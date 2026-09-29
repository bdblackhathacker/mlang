CC=gcc
CFLAGS=-m32 -ffreestanding -nostdlib -nostartfiles -nodefaultlibs -Wall -O2 -c
all: kernel.elf
boot.o: boot.S
	$(CC) $(CFLAGS) boot.S -o boot.o
kernel.o: kernel.c
	$(CC) $(CFLAGS) kernel.c -o kernel.o
kernel.elf: boot.o kernel.o linker.ld
	ld -m elf_i386 -T linker.ld boot.o kernel.o -o kernel.elf
	@echo "kernel.elf built (multiboot, i386). No grub/qemu on this box: iso/run skipped."
run: kernel.elf
	qemu-system-i386 -kernel kernel.elf -display curses || qemu-system-x86_64 -kernel kernel.elf -display curses || echo "install qemu to run"
iso: kernel.elf
	grub-mkrescue -o mlang.iso iso 2>/dev/null || echo "no grub-mkrescue; kernel.elf is the artifact"
clean:
	rm -rf boot.o kernel.o kernel.elf iso mlang.iso
