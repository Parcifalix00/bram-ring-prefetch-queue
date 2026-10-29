/* Complete-digest entry point; no default work, network or mining mode. */
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#define main inherited_diagnostic_main_not_called
#include SOURCE_FILE
#undef main
#define MAX_COUNT 4096u
#define MAX_THREADS 8u
static int number(const char *s, unsigned base, uint64_t *out) {
    if (!s || !*s || *s=='-' || *s=='+') return 0;
    errno=0; char *end; unsigned long long v=strtoull(s,&end,base);
    if (errno || *end) return 0;
    *out=(uint64_t)v; return 1;
}
static void full_hash(uint64_t nonce,uint32_t out[B],char digest[65]) {
    hash_state(nonce,out); /* init + full DEPTH fill + STEPS run */
    state_digest(out,digest); /* serialization + SHA-256 */
}
static uint64_t consume(uint64_t nonce,const char digest[65]) {
    uint64_t x=UINT64_C(14695981039346656037);
    for (unsigned i=0;i<64;i++) { x^=(unsigned char)digest[i]; x*=UINT64_C(1099511628211); }
    return x ^ nonce;
}
static int vector_mode(const char *path) {
    FILE *f=fopen(path,"r"); if(!f) return 3;
    char line[8192],nh[32],expected_digest[80],expected_fold[32],expected_state[4096],extra[2];
    unsigned seen=0;
    while(fgets(line,sizeof line,f)) {
        if(line[0]=='#' || strspn(line," \t\r\n")==strlen(line)) continue;
        if(!strchr(line,'\n') && !feof(f)) { fclose(f); return 4; }
        if(sscanf(line,"%31s %79s %31s %4095s %1s",nh,expected_digest,expected_fold,expected_state,extra)!=4) { fclose(f); return 4; }
        uint64_t nonce,fold;
        if(!number(nh,16,&nonce)||!number(expected_fold,16,&fold)||fold>UINT32_MAX) { fclose(f); return 4; }
        uint32_t out[B]; char digest[65],state[B*((W+3)/4)+1];
        full_hash(nonce,out,digest);
        char *p=state; for(int b=B-1;b>=0;b--) p+=sprintf(p,"%0*x",(W+3)/4,out[b]);
        if(strcmp(digest,expected_digest)||difficulty_value(out)!=(uint32_t)fold||strcmp(state,expected_state)) { fprintf(stderr,"VECTOR_MISMATCH nonce=%016" PRIx64 "\n",nonce); fclose(f); return 5; }
        printf("%016" PRIx64 " %s %08x %s\n",nonce,digest,difficulty_value(out),state);
        seen++;
    }
    int bad=ferror(f); fclose(f);
    if(bad||!seen) return 4;
    return 0;
}
static int bench_mode(uint64_t count,unsigned threads,uint64_t first) {
    if(!count||count>MAX_COUNT||!threads||threads>MAX_THREADS||first>UINT64_MAX-(count-1)) return 2;
    build_tables(); /* one-time epoch preparation, outside measured interval */
    uint64_t checksum=0,done=0; int actual_threads=0;
    omp_set_dynamic(0);
    double t0=now();
    #pragma omp parallel num_threads(threads) reduction(^:checksum) reduction(+:done)
    {
        #pragma omp single
        actual_threads=omp_get_num_threads();
        #pragma omp for schedule(static)
        for(uint64_t i=0;i<count;i++) {
            uint32_t out[B]; char digest[65];
            uint64_t nonce=first+i;
            full_hash(nonce,out,digest);
            checksum ^= consume(nonce,digest);
            done++;
        }
    }
    double seconds=now()-t0;
    if(done!=count||actual_threads!=(int)threads||!(seconds>0)) return 6;
    printf("{\"mode\":\"bounded_complete_digest\",\"count\":%" PRIu64 ",\"threads\":%d,\"first_nonce_hex\":\"%016" PRIx64 "\",\"checksum_hex\":\"%016" PRIx64 "\",\"wall_seconds\":%.9f,\"work\":\"init+fill+run+serialize+SHA256+consume\",\"rate_claim\":false}\n",done,actual_threads,first,checksum,seconds);
    return 0;
}
int main(int argc,char **argv) {
    if(argc==3&&!strcmp(argv[1],"vectors")) return vector_mode(argv[2]);
    if(argc==5&&!strcmp(argv[1],"bench")) {
        uint64_t count,threads,first;
        if(!number(argv[2],10,&count)||!number(argv[3],10,&threads)||!number(argv[4],16,&first)||threads>UINT_MAX) return 2;
        return bench_mode(count,(unsigned)threads,first);
    }
    if(argc==2&&!strcmp(argv[1],"sha-control")) {
        uint8_t digest[32]; sha256(digest,(const uint8_t*)"abc",3);
        for(unsigned i=0;i<32;i++) printf("%02x",digest[i]);
        printf("\n"); return 0;
    }
    fprintf(stderr,"usage: vectors FILE | bench COUNT(1..4096) THREADS(1..8) FIRST_NONCE_HEX | sha-control\n");
    return 2;
}