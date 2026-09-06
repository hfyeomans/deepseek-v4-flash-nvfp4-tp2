# Direct integration plan

1. Fetch all recipe branches and check both worktrees for unsaved work.
2. Verify that every source tip is contained in the selected integration tip.
3. Save and verify a complete Git recovery bundle. Retain branches and worktrees.
4. Create `main` from the tip containing all work. Reconcile current branch
   references in the docs while preserving historical measurement context.
5. Run local checks and the documentation scan on `main`.
6. Push `main`, make it the default branch, and verify remote ancestry and CI.
   Keep the repository private and leave GPU services untouched.
