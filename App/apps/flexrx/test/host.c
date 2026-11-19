/* Host harness: runs flexrx_app.c on the PC with a mock app_api_t fed from a
 * 12.8 kHz sample file (uint16 LE, flex.py). Time is modelled in 48 MHz
 * cycles; a key scan costs 0.3 ms and a screen blit 12 ms, as on the radio.
 *   cc -O1 -o host host.c && ./host t.raw ../flexrx_assets.bin */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#define FLEXRX_HOST
static void flexrx_host_dump(void);
static int verbose;
static uint64_t cyc;
static void flexrx_host_cost(unsigned c){ cyc+=c; }
#include "../flexrx_app.c"

static uint16_t *aud; static size_t naud;
static uint8_t fbuf[8][128], sline[128];
static uint8_t assets[4096]; static size_t nassets;
static char lastBottom[64];
static int draws, nbeeps, nlight; static char beeplog[256];

static uint32_t m_clk(void){ cyc+=40; return (uint32_t)cyc; }
static uint16_t m_sample(void){ size_t i=cyc/CYC_PER_SAMPLE; return i<naud?aud[i]:2048; }
/* KEYS="2000:10,2300:1,...": key codes pressed at those ms, held 150 ms */
static uint8_t m_key(void){
    cyc+=14400;
    if(cyc/CYC_PER_SAMPLE>=naud) return APP_KEY_EXIT;
    const char*k=getenv("KEYS"); uint32_t now=(uint32_t)(cyc/48000);
    while(k&&*k){ uint32_t t=strtoul(k,(char**)&k,10); k++; uint32_t c=strtoul(k,(char**)&k,10);
        if(now>=t&&now<t+150) return (uint8_t)c; if(*k==',')k++; }
    return APP_KEY_INVALID;
}
static void m_v(void){}
static void m_bl(void){ nlight++; }
static void m_tone(uint16_t hz,uint16_t ms){ (void)hz; cyc+=(uint64_t)ms*48000; nbeeps++; }
static void m_toff(void){ size_t l=strlen(beeplog); snprintf(beeplog+l,sizeof beeplog-l,"%d ",nbeeps); nbeeps=0; }
static void m_blit(void){ cyc+=576000; draws++; }
static void m_vb(bool b){(void)b;}
static void m_v8(uint8_t b){(void)b;}
static void m_d(uint32_t ms){ cyc+=(uint64_t)ms*48000; }
static uint32_t m_ticks(void){ return (uint32_t)(cyc/48000); }
static int16_t m_rssi(void){ return -87; }
static uint32_t m_freq(void){ return 16965000; }
static uint16_t m_bkr(uint8_t r){(void)r; return 0;}
static void m_bkw(uint8_t r,uint16_t v){(void)r;(void)v;}
static uint8_t saved[16]; static int nsaved;
static void m_cfgl(uint8_t*b,uint8_t n){
    memset(b,0xFF,n);
    /* CAPS="1530010,1520003": saved capcodes, as the radio's config holds them */
    const char*c=getenv("CAPS"); int i=0;
    while(c&&*c&&i<4){ uint32_t v=strtoul(c,(char**)&c,10); memcpy(b+4*i,&v,4); b[4*i+3]=0xFF; i++; if(*c==',')c++; }
}
static void m_cfgs(const uint8_t*b,uint8_t n){ memcpy(saved,b,n); nsaved=n; }
static char *m_i32(char*o,int32_t v){ return o+sprintf(o,"%d",v); }
static uint16_t m_asset(uint16_t off,void*b,uint16_t n){ memcpy(b,assets+off,n); return n; }
static void m_tiny(const char*s,uint8_t x,uint8_t y,bool sb,bool f){(void)x;(void)sb;(void)f; if(y==49) snprintf(lastBottom,sizeof lastBottom,"%s",s);}
static void m_bold(const char*s,uint8_t a,uint8_t b,uint8_t l){(void)s;(void)a;(void)b;(void)l;}
static void m_inv(const char*s,uint8_t x,uint8_t l,bool sb,bool f,uint8_t e){(void)s;(void)x;(void)l;(void)sb;(void)f;(void)e;}
static void m_df(uint32_t f,uint8_t x,uint8_t l){(void)f;(void)x;(void)l;}

int main(int argc,char**argv){
    verbose=argc>3;
    FILE*f=fopen(argv[1],"rb"); fseek(f,0,SEEK_END); naud=ftell(f)/2; rewind(f);
    aud=malloc(naud*2); fread(aud,2,naud,f); fclose(f);
    f=fopen(argv[2],"rb"); nassets=fread(assets,1,sizeof assets,f); fclose(f);
    static app_api_t api;
    api.fb=fbuf; api.status_line=sline;
    api.display_clear=m_v; api.status_clear=m_v; api.print_inverse=m_inv; api.draw_battery=m_v;
    api.print_bold=m_bold; api.print_tiny=m_tiny; api.print_normal=m_bold; api.asset_read=m_asset;
    api.draw_frequency=m_df; api.rx_freq=m_freq; api.ticks_ms=m_ticks; api.rssi_dbm=m_rssi;
    api.get_key=m_key; api.led=m_vb; api.backlight_on=m_bl; api.backlight_update=m_v;
    api.battery_sample=m_v; api.blit_status=m_v; api.blit_full=m_blit; api.audio_path=m_vb;
    api.append_i32=m_i32; api.af_capture_open=m_v; api.af_capture_sample=m_sample;
    api.af_capture_close=m_v; api.cycles_48mhz=m_clk; api.bk_read=m_bkr; api.bk_write=m_bkw;
    api.cfg_load=m_cfgl; api.cfg_save=m_cfgs; api.set_af=m_v8; api.delay_ms=m_d; api.play_tone=m_tone; api.tones_off_rx=m_toff;
    /* app_main keeps the pages on its stack: dump them from a hook at exit */
    app_main(&api);
    return 0;
}

static void flexrx_host_frame(void){
    if(!verbose) return;
    printf("frame %u: good %u, corrected %u, bad at:",g.frame,g.good,0);
    for(int i=0;i<NWORDS;i++) if(!g.fq[i]) printf(" %d",i);
    printf("\n");
}
static void flexrx_host_dump(void){
    printf("frames %u  pages %u  last good %u  mode %u  draws %d\n",g.nFrames,g.nOk,g.good,g.mode,draws);
    printf("bottom: %s\n",lastBottom);
    printf("saved %d B:",nsaved); for(int i=0;i<4;i++){ uint32_t v; memcpy(&v,saved+4*i,4); printf(" %u/top%u",v&0xFFFFFF,v>>24); } printf("\n");
    printf("beeps: %s  light: %d (1 at launch)\n",beeplog,nlight);
    for(int k=g.count-1;k>=0;k--){
        page_t*p=g.history[k];
        printf("  %07u %s +%u \"",p->ric,p->type==V_ALPHA?"ALN":"NUM",p->extra);
        for(int i=0;i<p->len;i++) putchar((uint8_t)p->text[i]==GAP?'?':p->text[i]);
        printf("\"\n");
    }
}
