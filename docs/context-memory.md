# Understanding the context-memory results

## Why a larger window reports more cache tokens

The reported token count is a calculation based on the configured request length.
It is not a count of identical, uncompressed token slots in GPU memory. The two
observed startup reports reproduce exactly from the pinned runtime's formula:

| Configured window | Available KV memory | Pool blocks | Blocks per request | Cache concurrency | Reported tokens |
|---:|---:|---:|---:|---:|---:|
| 65,536 | 6.11 GiB | 6,547 | 1,946 | 3.364337 | 220,485 |
| 801,000 | 5.22 GiB | 5,589 | 4,819 | 1.159784 | 928,987 |

For these two configurations:

```text
blocks per request = ceil(context window / 256) + 1690
cache concurrency  = pool blocks / blocks per request
reported tokens    = floor(cache concurrency × context window)
```

The 1,690 blocks are a fixed working area at these lengths. Longer requests
spread that cost over more tokens. The displayed total can therefore increase
while the physical pool becomes smaller. Reading the 64K report as a maximum
possible context would give the wrong conclusion.

The [reporting code](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L922)
divides the pool by the charged blocks per request and then multiplies by the
configured maximum length. The allocator chooses the smallest available block
count across the TP ranks. TP=2 does not simply double this pool.

## What occupies those blocks

DeepSeek V4 combines sliding windows with compressed history. Its full-history
group contains 21 C4 attention caches, 21 accompanying FP8 indexer caches, and
20 C128 attention caches. Compression reduces the stored rows per page. In this
packed layout, a physical pool block is 1,002,240 bytes:

```text
21 × (37,440 + 8,640) + 20 × 1,728 = 1,002,240 bytes
```

The fixed working charge includes two sliding-window groups (134 blocks), C4
compressor state (1,027), and C128 compressor state (529). Its 4,096 in-flight
tokens come from two asynchronous batches of 2,048 tokens. Changing batch or
scheduling settings can change this working charge, so the simplified formula
above must not be applied blindly to another launch.

See the [cache-spec layout](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/kv_cache_interface.py#L391)
and [sliding-window sizing](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/kv_cache_interface.py#L590).

## Why startup and retrieval remain separate tests

The 801K profile consumed more non-KV memory: weights plus non-Torch allocation
rose from 83.47 to 84.35 GiB, measured activation peak from 0.67 to 0.69 GiB, and
estimated graph memory from 0.19 to 0.21 GiB. The logs do not identify one buffer
as the cause. Re-profile each context setting instead of assuming a constant
available KV budget.

This pinned build also has a separate conservative startup check. Its
[padded calculation](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L1888)
charges 1,099,584 bytes per block, compared with the packed allocator's
1,002,240. Thus 928,987 reported tokens is neither an automatic fit limit nor
proof that another context setting will start.

The allocated 801K window passed actual retrieval from 799,847 prompt tokens
([evidence](../results/dspark-801k-features.json)). The separate 1M/96% attempt
also passed retrieval from 998,847 prompt tokens
([evidence](../results/dspark-1m-96-features.json)). Cache concurrency is
also separate from the two configured sequence slots; successful short-request
concurrency does not prove that two near-full 801K requests fit simultaneously.
