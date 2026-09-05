# Understanding the context-memory results

## Why a larger window reports more cache tokens

Reported cache tokens depend on the configured request length. They do not
count identical uncompressed slots. Both startup reports match the pinned
runtime formula:

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

At these lengths,1,690 blocks cover fixed workspace. Longer requests spread
that charge over more tokens, so the displayed token total can grow while
the physical pool shrinks. The 64K report is not a maximum context limit.

The [reporting code](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L922)
divides pool blocks by blocks charged per request, then multiplies by maximum
length. Allocation uses the smallest rank's block count; TP=2 does not double
that pool.

## What occupies those blocks

DeepSeek V4 combines sliding windows and compressed history. Its full-history
group has 21 C4 attention caches,21 FP8 indexer caches and 20 C128 attention
caches. Compression reduces rows/page. One packed pool block is 1,002,240 bytes:

```text
21 × (37,440 + 8,640) + 20 × 1,728 = 1,002,240 bytes
```

Fixed workspace includes sliding windows (134 blocks), C4 compressor state
(1,027) and C128 state (529). Two asynchronous batches of 2,048 account for 4,096
in-flight tokens. Changing batch or scheduling changes this charge; recompute
for other settings.

See the [cache-spec layout](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/kv_cache_interface.py#L391)
and [sliding-window sizing](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/kv_cache_interface.py#L590).

## Why startup and retrieval remain separate tests

At 801K, weights plus non-Torch allocation rose from 83.47 to 84.35 GiB, activation
peak from 0.67 to 0.69 GiB and graph estimate from 0.19 to 0.21 GiB. Logs do not
identify the buffer responsible. Reprofile each context setting.

The separate [startup admission check](https://github.com/jasl/vllm/blob/0f59188db1504b042ce621842bdde6c0fe862df6/vllm/v1/core/kv_cache_utils.py#L1888)
charges 1,099,584 bytes/block versus 1,002,240 for packed allocation. The reported
928,987 tokens therefore cannot predict whether another setting will start.

The 801K profile retrieved from 799,847 prompt tokens
([evidence](../results/dspark-801k-features.json)); the 1M/96% profile retrieved
from 998,847 ([evidence](../results/dspark-1m-96-features.json)). Two configured
slots and passing short-request concurrency do not prove two full 801K requests
fit together.
