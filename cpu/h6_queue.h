#ifndef NEXA_H6_QUEUE_H
#define NEXA_H6_QUEUE_H
#include <stdint.h>
#include <immintrin.h>

/* Private H6: consume block i-2 before enqueue i; D=2, two slots. */
typedef struct {
    uint32_t qv[2][8];
    uint32_t qa[2][8];
} h4_queue;
_Static_assert(sizeof(h4_queue) == 128, "H6 queue payload must be 128 bytes");
_Static_assert(B == 768 && DEPTH == 512, "H6 geometry must match H4");

static inline void h4_enqueue_block(h4_queue *q, int block, __m256i v8,
                                    uint32_t bank[B][DEPTH],
                                    const uint32_t amask[B])
{
    int slot = block & 1;
    _mm256_storeu_si256((__m256i *)q->qv[slot], v8);
    for (int k = 0; k < 8; k++) {
        int b = block * 8 + k;
        unsigned a = _pext_u32(q->qv[slot][k], amask[b]);
        q->qa[slot][k] = a;
        _mm_prefetch((const char *)&bank[b][a], _MM_HINT_T0);
    }
}

/* Nonnegative blocks; caller must consume before reusing either slot. */
static inline void h4_consume_block(h4_queue *q, int block,
                                    uint32_t bank[B][DEPTH], uint32_t nrd[B])
{
    int slot = block & 1;
    for (int k = 0; k < 8; k++) {
        int b = block * 8 + k;
        unsigned a = q->qa[slot][k];
        uint32_t old = bank[b][a];
        nrd[b] = old;
        bank[b][a] = q->qv[slot][k];
    }
}
#endif
