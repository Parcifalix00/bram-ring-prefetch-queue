#ifndef NEXA_H4_QUEUE_H
#define NEXA_H4_QUEUE_H
#include <stdint.h>
#include <immintrin.h>

/* Fixed D=2, three slots. Bank layout and logical work stay unchanged. */
typedef struct {
    uint32_t qv[3][8];
    uint32_t qa[3][8];
} h4_queue;
_Static_assert(sizeof(h4_queue) == 192, "H4 queue payload must be 192 bytes");
_Static_assert(B == 768 && DEPTH == 512, "H4 reviewed geometry only");

static inline void h4_enqueue_block(h4_queue *q, int block, __m256i v8,
                                    uint32_t bank[B][DEPTH],
                                    const uint32_t amask[B])
{
    int slot = block % 3;
    _mm256_storeu_si256((__m256i *)q->qv[slot], v8);
    for (int k = 0; k < 8; k++) {
        int b = block * 8 + k;
        unsigned a = _pext_u32(q->qv[slot][k], amask[b]);
        q->qa[slot][k] = a;
        _mm_prefetch((const char *)&bank[b][a], _MM_HINT_T0);
    }
}

/* Shared by the candidate kernel, sentinel unit and disassembly probe. */
static inline void h4_consume_block(h4_queue *q, int block,
                                    uint32_t bank[B][DEPTH], uint32_t nrd[B])
{
    int slot = block % 3;
    for (int k = 0; k < 8; k++) {
        int b = block * 8 + k;
        unsigned a = q->qa[slot][k];
        uint32_t old = bank[b][a];
        nrd[b] = old;
        bank[b][a] = q->qv[slot][k];
    }
}
#endif
