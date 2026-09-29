/* MLANG stub kernel - freestanding, no libc. Proves boot path only. */
volatile unsigned short *VGA = (unsigned short*)0xB8000;
void kprint(const char *s) {
  for (int i = 0; s[i]; i++) VGA[i] = 0x0F00 | s[i];
}
void kmain(void) {
  kprint("MLANG kernel stub: replace kprint with Val runtime for full MLang.");
  for (;;) __asm__ volatile("hlt");
}
