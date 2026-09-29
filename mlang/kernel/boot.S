	.code32
	.global _start
	.extern kmain
	.section .multiboot
	.align 4
	.long 0x1BADB002
	.long 0x00
	.long -(0x1BADB002)
	.section .text
_start:
	cli
	call kmain
hang:
	hlt
	jmp hang
