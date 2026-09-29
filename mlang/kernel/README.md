# MLang kernel (stub)

This is a bootable stub proving the kernel path, not a full MLang kernel.

- `boot.s` multiboot header + `_start` -> `kmain`
- `kernel.c` freestanding VGA print, no libc
- Full MLang-on-bare-metal needs: Val runtime without `malloc/printf/fopen`,
  static arena allocator, serial/VGA drivers, syscalls. Months of work.
