// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stddef.h>
#include <assert.h>
#include "network_setup.h"
#include "header.h"
#include "block.h"

struct loader_block {
  uint32_t rom_size_word;
  union {
    struct header header;
    uint8_t pad[HEADER_MAX_BYTES];
  } header;
  uint8_t loader[BLOCK_SIZE - HEADER_MAX_BYTES - 8];
  uint32_t crc_disable_magic;
};

void establish_image_block_counts(unsigned image_block_count[2],
                                  FILE *ftile0, FILE *ftile1)
{
  fseek(ftile0, 0, SEEK_END);
  fseek(ftile1, 0, SEEK_END);
  image_block_count[0] = (unsigned)ftell(ftile0) / BLOCK_SIZE + 1;
  image_block_count[1] = (unsigned)ftell(ftile1) / BLOCK_SIZE + 1;
  fseek(ftile0, 0, SEEK_SET);
  fseek(ftile1, 0, SEEK_SET);
}

void fill_in_loader_block(struct loader_block *loader_block, FILE *floader,
                         const unsigned image_block_count[2])
{
  memset(loader_block, 0, BLOCK_SIZE);

  size_t ret = fread(&loader_block->header,
    1, BLOCK_SIZE - HEADER_MAX_BYTES - 8, floader);

  assert(!ferror(floader));
  printf("%zd loader object bytes (includes header but not ROM size word)\n", ret);

  const int trampoline_offset = HEADER_MAX_BYTES - 2;
  
  // information manually collected from various places
  // mostly xntools network graph
  // also xobjdump resources and dirBits0 in disassembly
  // all of this could be automated
  // trampoline is BU NOP (BU encoding is xy 73, NOP encoding FF 17)
  struct header header = {
    .trampoline = 0x17FF7300 + trampoline_offset / 2,
    .network_info = {
      .usb_link = {8, 1, 52},
      .user_routing = {0x22222102, 0x22222222},
      .user_id = 0x8002,
      .usb_id = 0x8006,
      .pll_ctl = 0xc702,
      .ref_div = 7
    },
    .image_block_count = {image_block_count[0], image_block_count[1]}
  };

  loader_block->rom_size_word = BLOCK_SIZE / 4 - 2,
  loader_block->header.header = header;
  loader_block->crc_disable_magic = 0x0D15AB1E;
}

void copy_file_with_padding(FILE *ftile, FILE *foutput, unsigned image_block_count)
{
  char block[BLOCK_SIZE];
  unsigned so_far = 0;

  while (!feof(ftile)) {
    memset(block, 0, BLOCK_SIZE);
    size_t ret = fread(block, 1, BLOCK_SIZE, ftile);
    assert(!ferror(ftile));
    fwrite(block, 1, BLOCK_SIZE, foutput);
    so_far++;
  }

  memset(block, 0, BLOCK_SIZE);
  while (so_far < image_block_count) {
    fwrite(block, 1, BLOCK_SIZE, foutput);
    so_far++;
  }

  printf("%zd image bytes\n", ftell(ftile));
}

int main(int argc, char **argv)
{
  // packing sanity checks
  assert(sizeof(struct loader_block) == BLOCK_SIZE);
  assert(offsetof(struct loader_block, loader) == HEADER_MAX_BYTES + 4);
  assert(offsetof(struct loader_block, crc_disable_magic) == BLOCK_SIZE - 4);

  if (argc != 5) {
    fprintf(stderr, "usage: %s LOADER-BIN TILE0-BIN TILE1-BIN OUTPUT-BIN\n", argv[0]);
    exit(2);
  }
  
  FILE *floader = fopen(argv[1], "rb");
  FILE *ftile0 = fopen(argv[2], "rb");
  FILE *ftile1 = fopen(argv[3], "rb");
  FILE *foutput = fopen(argv[4], "wb");

  if (floader == NULL || ftile0 == NULL || ftile1 == NULL || foutput == NULL) {
    fprintf(stderr, "Error: Invalid input argument\n");
    exit(1);
  }

  unsigned image_block_count[2];
  establish_image_block_counts(image_block_count, ftile0, ftile1);

  struct loader_block loader_block;
  fill_in_loader_block(&loader_block, floader, image_block_count);

  // Write two loader blocks - one for each tile
  fwrite(&loader_block, 1, BLOCK_SIZE, foutput);
  fwrite(&loader_block, 1, BLOCK_SIZE, foutput);

  copy_file_with_padding(ftile1, foutput, image_block_count[1]);
  copy_file_with_padding(ftile0, foutput, image_block_count[0]);

  unsigned transfer_block_num = 2 + image_block_count[1];
  printf("transfer_block_num: %u\n", transfer_block_num);

  fclose(floader);
  fclose(ftile0);
  fclose(ftile1);
  fclose(foutput);

  return 0;
}
