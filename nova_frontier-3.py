"""
NOVA FRONTIER v3.0 — Android Pydroid3 / Pygame 2.x
Полноэкранный горизонтальный режим, джойстики, планшет-меню
"""
import pygame, sys, math, random, json, os, socket, threading

pygame.init()
info = pygame.display.Info()
SW = max(info.current_w, info.current_h)
SH = min(info.current_w, info.current_h)
if SW <= 0: SW = 800
if SH <= 0: SH = 480
screen = pygame.display.set_mode((SW, SH), pygame.FULLSCREEN)
pygame.display.set_caption("NOVA FRONTIER")

TILE = 32
FPS  = 30

C_BG    =(4,8,18);  C_GRID=(12,28,48); C_FRAME=(0,170,255)
C_DIM   =(0,70,130);C_TEXT=(170,220,255);C_TEXT2=(90,150,195)
C_WARN  =(255,175,0);C_DANGER=(255,45,45);C_GREEN=(40,210,90)
C_NIGHT =(0,4,14)
C_GP    =(180,40,255); C_GB=(40,100,255); C_GR=(255,40,80)

def _mkfont(sz):
    for nm in ["monospace","courier","couriernew",None]:
        try:
            f = pygame.font.SysFont(nm,sz,bold=True) if nm else pygame.font.Font(None,sz+4)
            f.render("A",True,(255,255,255)); return f
        except: pass
    return pygame.font.Font(None,sz+4)

# Масштаб шрифтов под размер экрана (базовый экран 480px высота)
_FSCALE = max(1.0, SH / 480.0)
def _fs(sz): return _mkfont(int(sz * _FSCALE))

FS=_fs(14); FM=_fs(18); FL=_fs(23); FXL=_fs(32)

# Масштаб UI элементов
def us(v): return int(v * _FSCALE)  # ui scale

def cl(v,lo,hi): return max(lo,min(hi,v))
def sc(c):
    if len(c)==3: return (cl(int(c[0]),0,255),cl(int(c[1]),0,255),cl(int(c[2]),0,255))
    return (cl(int(c[0]),0,255),cl(int(c[1]),0,255),cl(int(c[2]),0,255),cl(int(c[3]),0,255))
def lc(a,b=None,t=None):
    # Safe: if called as lc(color) just return sc(color)
    if b is None: return sc(a)
    if t is None: return sc(a)
    t=cl(t,0.0,1.0)
    return sc((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t))
def d2(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])

def txt(surf,s,pos,font=None,color=None,center=False,shadow=False):
    if font is None:  font=FM
    if color is None: color=C_TEXT
    color=sc(color)
    img=font.render(str(s),True,color)
    x=pos[0]-(img.get_width()//2 if center else 0)
    y=pos[1]
    if shadow:
        si=font.render(str(s),True,(0,0,0))
        surf.blit(si,(x+1,y+1))
    surf.blit(img,(x,y))

def dpanel(surf,rect,alpha=200,col=None):
    x,y,w,h=int(rect[0]),int(rect[1]),int(rect[2]),int(rect[3])
    if w<=0 or h<=0: return
    s=pygame.Surface((w,h),pygame.SRCALPHA); s.fill((5,14,30,alpha))
    surf.blit(s,(x,y))
    pygame.draw.rect(surf,col if col else C_FRAME,(x,y,w,h),2,border_radius=5)

def dbtn(surf,rect,label,active=False,hover=False,font=None,danger=False):
    if font is None: font=FM
    fc=C_DANGER if danger else(C_GREEN if active else(C_FRAME if hover else C_DIM))
    dpanel(surf,rect,alpha=210,col=fc)
    txt(surf,label,(rect[0]+rect[2]//2,rect[1]+rect[3]//2),font,fc,center=True)

# ── Terrain ──
TR_SAND=0; TR_STONE=1; TR_ICE=2
T_FLOOR=0;T_SAND1=1;T_SAND2=2;T_CRACK=3;T_ROCK=4;T_MOUND=5

TR_PAL={
    TR_SAND:{
        T_FLOOR:[(195,158,72),(178,142,58),(162,126,44)],
        T_SAND1:[(210,172,85),(195,158,72),(178,142,58)],
        T_SAND2:[(175,138,52),(160,124,40),(148,112,32)],
        T_CRACK:[(50,38,22),(40,30,15),(32,24,10)],
        T_ROCK: [(110,95,70),(90,78,55),(75,62,42)],
        T_MOUND:[(145,118,60),(130,104,48),(115,92,38)],
    },
    TR_STONE:{
        T_FLOOR:[(82,84,92),(72,74,82),(65,67,75)],
        T_SAND1:[(95,98,108),(82,84,92),(72,74,82)],
        T_SAND2:[(70,72,80),(62,64,72),(55,57,65)],
        T_CRACK:[(30,30,35),(22,22,28),(15,15,20)],
        T_ROCK: [(55,58,68),(45,48,58),(38,40,50)],
        T_MOUND:[(100,105,115),(88,92,102),(78,82,92)],
    },
    TR_ICE:{
        T_FLOOR:[(168,208,228),(152,194,216),(140,182,206)],
        T_SAND1:[(182,218,238),(168,208,228),(152,194,216)],
        T_SAND2:[(148,188,208),(135,175,196),(124,164,186)],
        T_CRACK:[(60,80,100),(48,65,85),(38,52,70)],
        T_ROCK: [(90,115,135),(78,100,122),(68,88,110)],
        T_MOUND:[(145,178,200),(132,165,188),(120,152,178)],
    },
}

BLOCK={T_ROCK,T_CRACK}

class World:
    def __init__(self,w,h,terrain=TR_SAND):
        self.w=w;self.h=h;self.terrain=terrain
        self.passable=[[True]*w for _ in range(h)]
        self.objs={}
        self.height=[[0]*w for _ in range(h)]  # 0=пол, 1-4=горы, -1=расщелина
        self.C_FLOOR={TR_SAND:(188,152,68),TR_STONE:(72,76,86),TR_ICE:(152,192,218)}[terrain]
        self.C_CRACK={TR_SAND:(35,24,8),  TR_STONE:(18,18,24), TR_ICE:(40,58,82)}[terrain]
        self.C_MOUNT={TR_SAND:(138,108,50),TR_STONE:(52,55,65),TR_ICE:(105,138,168)}[terrain]
        self._tile_cache={}
        self._gen()
        self._build_cache()

    def _gen(self):
        rng=random.Random(55555)
        # Горы — кластеры высот
        for _ in range(25):
            cx=rng.randint(3,self.w-4); cy=rng.randint(3,self.h-4)
            peak=rng.randint(2,4); r=rng.randint(2,6)
            for dy in range(-r,r+1):
                for dx in range(-r,r+1):
                    dd=math.hypot(dx,dy)
                    if dd<=r:
                        tx=cl(cx+dx,0,self.w-1); ty=cl(cy+dy,0,self.h-1)
                        h2=int(peak*(1-dd/r))
                        self.height[ty][tx]=max(self.height[ty][tx],h2)
        # Расщелины
        for _ in range(10):
            cx=rng.randint(3,self.w-4); cy=rng.randint(3,self.h-4)
            ang=rng.uniform(0,math.pi*2); length=rng.randint(5,14)
            for step in range(length):
                ang+=rng.uniform(-0.5,0.5)
                tx=cl(cx+int(math.cos(ang)*step),0,self.w-1)
                ty=cl(cy+int(math.sin(ang)*step),0,self.h-1)
                self.height[ty][tx]=-1; self.passable[ty][tx]=False
        # Горы>=2 непроходимы
        for ty in range(self.h):
            for tx in range(self.w):
                if self.height[ty][tx]>=2: self.passable[ty][tx]=False
        # Ресурсы
        placed=0; att=0
        while placed<100 and att<3000:
            att+=1
            tx=rng.randint(2,self.w-3); ty=rng.randint(2,self.h-3)
            if self.passable[ty][tx] and (tx,ty) not in self.objs:
                self.objs[(tx,ty)]=rng.choice(["scrap","scrap","scrap","ore","ruin"])
                placed+=1
        # Расчистка старта
        for dy in range(-5,6):
            for dx in range(-5,6):
                tx=cl(20+dx,0,self.w-1); ty=cl(20+dy,0,self.h-1)
                self.height[ty][tx]=0; self.passable[ty][tx]=True
                if (tx,ty) in self.objs: del self.objs[(tx,ty)]
        # Расчистка зоны Веги
        for dy in range(-8,9):
            for dx in range(-12,13):
                tx=cl(38+dx,0,self.w-1); ty=cl(18+dy,0,self.h-1)
                self.height[ty][tx]=0; self.passable[ty][tx]=True
                if (tx,ty) in self.objs: del self.objs[(tx,ty)]

    def _build_cache(self):
        fc=self.C_FLOOR; mc=self.C_MOUNT; cc=self.C_CRACK
        # Пол — чистый цвет
        s=pygame.Surface((TILE,TILE)); s.fill(fc)
        self._tile_cache['floor']=s
        # Расщелина
        s=pygame.Surface((TILE,TILE)); s.fill(cc)
        bc2=sc((min(255,cc[0]+25),min(255,cc[1]+35),min(255,cc[2]+55)))
        pygame.draw.rect(s,bc2,(0,0,TILE,TILE),1)
        self._tile_cache['crack']=s
        # Горы 4 уровня — чем выше тем темнее, 3D кубик
        for h2 in range(1,5):
            t=h2/4
            base=lc(mc,sc((max(0,mc[0]-70),max(0,mc[1]-70),max(0,mc[2]-60))),t*0.75)
            s=pygame.Surface((TILE,TILE)); s.fill(base)
            top=sc((min(255,base[0]+40),min(255,base[1]+40),min(255,base[2]+30)))
            pygame.draw.rect(s,top,(0,0,TILE,TILE//3))
            left=sc((min(255,base[0]+18),min(255,base[1]+18),min(255,base[2]+12)))
            pygame.draw.rect(s,left,(0,0,TILE//4,TILE))
            right=sc((max(0,base[0]-28),max(0,base[1]-28),max(0,base[2]-22)))
            pygame.draw.rect(s,right,(TILE*3//4,0,TILE//4,TILE))
            outline=sc((max(0,base[0]-45),max(0,base[1]-45),max(0,base[2]-40)))
            pygame.draw.rect(s,outline,(0,0,TILE,TILE),1)
            self._tile_cache[f'mount{h2}']=s

    def is_passable(self,wx,wy):
        tx=int(wx//TILE); ty=int(wy//TILE)
        if tx<0 or ty<0 or tx>=self.w or ty>=self.h: return False
        return self.passable[ty][tx]

    def draw(self,surf,cx,cy,night):
        x0=cx//TILE; y0=cy//TILE
        cols=SW//TILE+2; rows=SH//TILE+2
        for row in range(rows):
            for col in range(cols):
                tx=x0+col; ty=y0+row
                if not(0<=tx<self.w and 0<=ty<self.h): continue
                rx=col*TILE-(cx%TILE); ry=row*TILE-(cy%TILE)
                h2=self.height[ty][tx]
                key='crack' if h2==-1 else (f'mount{min(h2,4)}' if h2>=1 else 'floor')
                ts=self._tile_cache.get(key)
                if ts: surf.blit(ts,(rx,ry))
                k=(tx,ty)
                if k in self.objs: self._dobj(surf,self.objs[k],rx,ry,night)
        if night>0.05:
            if not hasattr(self,'_ns') or self._ln!=int(night*170):
                self._ln=int(night*170)
                self._ns=pygame.Surface((SW,SH),pygame.SRCALPHA)
                self._ns.fill((0,4,14,self._ln))
            surf.blit(self._ns,(0,0))

    def _dobj(self,surf,obj,rx,ry,night):
        nm=C_NIGHT
        if obj=="scrap":
            c=lc((210,195,130),nm,night)
            pts=[(rx+6,ry+6),(rx+24,ry+8),(rx+22,ry+24),(rx+4,ry+22)]
            pygame.draw.polygon(surf,c,pts)
            pygame.draw.polygon(surf,lc((120,108,65),nm,night),pts,2)
            pygame.draw.line(surf,lc((240,225,160),nm,night),(rx+8,ry+9),(rx+16,ry+14),2)
        elif obj=="ore":
            for i in range(3):
                ox=rx+7+i*6; oy=ry+10+abs(i-1)*4
                pygame.draw.circle(surf,lc((0,200,255),nm,night),(ox,oy),6-i)
                pygame.draw.circle(surf,lc((120,245,255),nm,night),(ox-1,oy-1),2)
        elif obj=="ruin":
            c=lc((92,72,52),nm,night)
            pygame.draw.rect(surf,c,(rx+2,ry+10,24,16))
            pygame.draw.rect(surf,lc((55,40,28),nm,night),(rx+2,ry+10,24,16),2)
            pygame.draw.rect(surf,lc((112,90,62),nm,night),(rx+6,ry+3,10,10))

# ── Здания ──
B_HQ=0;B_DRILL=1;B_STORAGE=2;B_STUDY=3;B_ASSEMBLY=4
B_HOUSE=5;B_BARRACKS=6;B_SHIPYARD=7;B_ARMORY=8

BDATA={
    B_HQ:      {"name":"Штаб",          "cost":{"scrap":20},        "size":(2,2),"col":(0,100,200)},
    B_DRILL:   {"name":"Бур",           "cost":{"scrap":30},        "size":(2,2),"col":(180,100,0)},
    B_STORAGE: {"name":"Хранилище",     "cost":{"scrap":25,"ore":5},"size":(2,1),"col":(0,155,75)},
    B_ARMORY:  {"name":"Оружейная",     "cost":{"scrap":15,"ore":5},"size":(2,2),"col":(160,60,0)},
    B_STUDY:   {"name":"Центр изуч.",   "cost":{"ore":40,"scrap":20},"size":(3,2),"col":(80,0,200)},
    B_ASSEMBLY:{"name":"Сборщик ТС",    "cost":{"ore":50,"scrap":30},"size":(3,2),"col":(200,80,0)},
    B_HOUSE:   {"name":"Жилой дом",     "cost":{"ore":20,"scrap":15},"size":(2,2),"col":(0,100,160)},
    B_BARRACKS:{"name":"Казармы",       "cost":{"ore":30,"scrap":20},"size":(3,2),"col":(160,0,60)},
    B_SHIPYARD:{"name":"Верфь",         "cost":{"ore":100,"scrap":80},"size":(4,3),"col":(0,60,180)},
}

HG_LIST=["none","helmet","visor","antenna","goggles","sixeyes"]
HG_NAMES={"none":"Нет","helmet":"Шлем","visor":"Визор","antenna":"Антенна","goggles":"Очки","sixeyes":"* Шесть Глаз *"}
WEAPONS={"none":None,"pistol":{"name":"Пистолет","dmg":12,"rate":0.6,"col":(140,140,160)},
         "rifle":{"name":"Винтовка","dmg":22,"rate":0.35,"col":(80,80,100)},
         "blaster":{"name":"Бластер","dmg":35,"rate":0.5,"col":(0,200,200)}}

class Building:
    def __init__(self,btype,tx,ty):
        self.btype=btype;self.tx=tx;self.ty=ty
        d=BDATA[btype];self.name=d["name"];self.sw,self.sh=d["size"];self.col=d["col"]
        self.hp=100;self.max_hp=100;self.drill_t=0.0
    def srect(self,cx,cy): return(self.tx*TILE-cx,self.ty*TILE-cy,self.sw*TILE,self.sh*TILE)
    def draw(self,surf,cx,cy,night):
        nm=C_NIGHT;x,y,w,h=self.srect(cx,cy)
        if x>SW+64 or y>SH+64 or x+w<-64 or y+h<-64: return
        c=lc(self.col,nm,night)
        ts=pygame.Surface((w+4,h+4),pygame.SRCALPHA);ts.fill((0,0,0,55));surf.blit(ts,(x+3,y+3))
        pygame.draw.rect(surf,c,(x,y,w,h),border_radius=3)
        pygame.draw.rect(surf,lc(C_FRAME,nm,night),(x,y,w,h),2,border_radius=3)
        wc=lc((200,230,255),nm,night)
        for i in range(self.sw):
            pygame.draw.rect(surf,wc,(x+i*TILE+6,y+6,TILE-14,8),border_radius=2)
        hw=int((w-4)*self.hp/self.max_hp)
        pygame.draw.rect(surf,(40,0,0),(x+2,y+h-5,w-4,4))
        pygame.draw.rect(surf,lc(C_GREEN,nm,night),(x+2,y+h-5,hw,4))
        txt(surf,self.name[:8],(x+3,y+2),FS,lc(C_TEXT,nm,night))
    def update(self,dt,res):
        if self.btype==B_DRILL:
            self.drill_t+=dt
            if self.drill_t>=8.0:
                self.drill_t=0.0;res["ore"]=res.get("ore",0)+1;res["scrap"]=res.get("scrap",0)+1

class Character:
    def __init__(self,x,y,color,name="",is_player=False):
        self.x=float(x);self.y=float(y);self.color=sc(color);self.name=name
        self.is_player=is_player;self.speed=120 if is_player else 80
        self.hp=100;self.max_hp=100;self.headgear="none";self.weapon="none"
        self.fire_t=0.0;self.anim=0.0;self.moving=False;self.facing=0.0
        self.carry={};self.task=None;self.task_t=0.0;self.target=None
    def total_carry(self): return sum(self.carry.values())
    def draw(self,surf,cx,cy,night):
        sx=int(self.x-cx);sy=int(self.y-cy)
        if sx<-40 or sy<-40 or sx>SW+40 or sy>SH+40: return
        nm=C_NIGHT
        bc=lc(self.color,nm,night)
        # --- СКАФАНДР ---
        suit =lc(self.color,nm,night)
        suit2=lc(sc((max(0,self.color[0]-30),max(0,self.color[1]-30),max(0,self.color[2]-30))),nm,night)
        dark =lc((15,15,25),nm,night)
        boot =lc((25,30,50),nm,night)
        metal=lc((160,170,185),nm,night)
        glass=lc((100,200,255),nm,night)

        # Тень
        shd=pygame.Surface((32,10),pygame.SRCALPHA);shd.fill((0,0,0,50));surf.blit(shd,(sx-16,sy+14))

        # Ноги — толстые скафандровые штаны
        la=self.anim if self.moving else 0; ls=int(math.sin(la)*5)
        pygame.draw.rect(surf,suit2,(sx-8,sy+8,7,12+ls),border_radius=2)
        pygame.draw.rect(surf,boot,(sx-9,sy+18+ls,9,6),border_radius=2)
        pygame.draw.rect(surf,suit2,(sx+1,sy+8,7,12-ls),border_radius=2)
        pygame.draw.rect(surf,boot,(sx,sy+18-ls,9,6),border_radius=2)

        # Тело — округлый скафандр
        pygame.draw.ellipse(surf,suit,(sx-10,sy-4,20,16))
        # Нагрудник — более светлая полоса
        pygame.draw.rect(surf,lc(sc((min(255,self.color[0]+40),min(255,self.color[1]+40),min(255,self.color[2]+30))),nm,night),
                         (sx-6,sy-2,12,6),border_radius=2)
        # Блик на теле
        pygame.draw.line(surf,lc(sc((min(255,self.color[0]+80),min(255,self.color[1]+80),min(255,self.color[2]+60))),nm,night),
                         (sx-6,sy-1),(sx-3,sy+4),1)
        # Баллон на спине
        pygame.draw.rect(surf,metal,(sx+8,sy-2,5,10),border_radius=2)
        pygame.draw.rect(surf,lc((80,90,110),nm,night),(sx+8,sy-2,5,10),1,border_radius=2)

        # Руки — круглые скафандровые перчатки
        pygame.draw.circle(surf,suit,(sx-11,sy+2),5)
        pygame.draw.circle(surf,suit,(sx+11,sy+2),5)

        # Оружие
        cos_f=math.cos(self.facing);sin_f=math.sin(self.facing)
        if self.weapon!="none" and self.weapon in WEAPONS and WEAPONS[self.weapon]:
            wc2=lc(WEAPONS[self.weapon]["col"],nm,night)
            ex=sx+int(cos_f*20);ey=sy+int(sin_f*20)
            pygame.draw.line(surf,wc2,(sx+int(cos_f*10),sy+int(sin_f*10)),(ex,ey),4)
            pygame.draw.rect(surf,lc((60,65,80),nm,night),
                             (sx+int(cos_f*10)-2,sy+int(sin_f*10)-2,6,4),border_radius=1)
            pygame.draw.circle(surf,lc((220,230,255),nm,night),(ex,ey),2)
            if self.fire_t>0.08:
                pygame.draw.circle(surf,lc(C_WARN,nm,night),(sx+int(cos_f*23),sy+int(sin_f*23)),4)

        # ── ГЕРМОШЛЕМ ──
        # Основа шлема
        hcol=lc(sc((max(0,self.color[0]-20),max(0,self.color[1]-20),max(0,self.color[2]-10))),nm,night)
        pygame.draw.ellipse(surf,hcol,(sx-11,sy-28,22,22))
        # Большое стекло визора
        pygame.draw.ellipse(surf,lc((0,30,60),nm,night),(sx-8,sy-26,16,14))
        pygame.draw.ellipse(surf,glass,(sx-7,sy-25,14,12))
        # Блик на стекле
        pygame.draw.ellipse(surf,lc((200,235,255),nm,night),(sx-5,sy-24,5,4))
        # Контур шлема
        pygame.draw.ellipse(surf,lc((80,90,110),nm,night),(sx-11,sy-28,22,22),2)
        # Нашейный воротник
        pygame.draw.rect(surf,metal,(sx-8,sy-8,16,5),border_radius=2)
        pygame.draw.rect(surf,lc((80,90,110),nm,night),(sx-8,sy-8,16,5),1,border_radius=2)

        # Спец прибор из настроек (поверх шлема)
        self._dhg(surf,sx,sy,night)

        # Маркер игрока
        if self.is_player:
            pygame.draw.polygon(surf,lc(C_GREEN,nm,night),[(sx,sy-40),(sx-5,sy-32),(sx+5,sy-32)])
        elif self.name:
            txt(surf,self.name[:6],(sx-18,sy-44),FS,lc(C_TEXT2,nm,night))
        # HP бар
        hw=int(22*self.hp/self.max_hp)
        pygame.draw.rect(surf,(50,0,0),(sx-11,sy-46,22,3))
        pygame.draw.rect(surf,lc(C_GREEN,nm,night),(sx-11,sy-46,hw,3))

    def _dhg(self,surf,sx,sy,night):
        nm=C_NIGHT;hg=self.headgear
        if hg=="helmet":
            pygame.draw.ellipse(surf,lc((60,80,120),nm,night),(sx-9,sy-28,18,14))
            pygame.draw.ellipse(surf,lc((0,120,200),nm,night),(sx-6,sy-25,12,8),2)
            pygame.draw.arc(surf,lc((100,150,200),nm,night),(sx-9,sy-28,18,14),0,math.pi,2)
        elif hg=="visor":
            pygame.draw.rect(surf,lc((0,80,180),nm,night),(sx-8,sy-22,16,6),border_radius=2)
            pygame.draw.rect(surf,lc((0,160,255),nm,night),(sx-7,sy-21,14,4),border_radius=2)
        elif hg=="antenna":
            pygame.draw.line(surf,lc((120,120,140),nm,night),(sx,sy-22),(sx+5,sy-32),2)
            pygame.draw.circle(surf,lc(C_WARN,nm,night),(sx+5,sy-32),3)
            if int(pygame.time.get_ticks()/400)%2==0:
                pygame.draw.circle(surf,lc((255,220,50),nm,night),(sx+5,sy-32),5,1)
        elif hg=="goggles":
            for ox in[-4,4]:
                pygame.draw.circle(surf,lc((0,60,120),nm,night),(sx+ox,sy-16),4)
                pygame.draw.circle(surf,lc((0,180,255),nm,night),(sx+ox,sy-16),4,1)
            pygame.draw.line(surf,lc((80,80,100),nm,night),(sx-4,sy-16),(sx+4,sy-16),1)
        elif hg=="sixeyes":
            # Белые волосы
            wh=lc((240,240,245),nm,night)
            for i in range(-8,10,3):
                pygame.draw.line(surf,wh,(sx+i,sy-22),(sx+i,sy-30+abs(i)//2),2)
            pygame.draw.arc(surf,wh,(sx-9,sy-32,18,12),0,math.pi,3)
            # Повязка
            pygame.draw.rect(surf,lc((15,15,20),nm,night),(sx-9,sy-20,18,6),border_radius=1)
            # 6 светящихся точек
            t2=pygame.time.get_ticks()/600
            for i,oy in enumerate([-17,-19,-21]):
                for ox2,bc3 in [(-8,C_GB),(8,C_GP)]:
                    pulse=int(abs(math.sin(t2+i*0.7))*60)+120
                    pygame.draw.circle(surf,sc((bc3[0],bc3[1],bc3[2])),(sx+ox2,sy+oy),2)

    def _moveto(self,tx,ty,dt,world=None):
        dx=tx-self.x;dy=ty-self.y;d=math.hypot(dx,dy)
        if d<3: self.moving=False; return True
        nx=self.x+dx/d*self.speed*dt;ny=self.y+dy/d*self.speed*dt
        if world is None or world.is_passable(nx,ny):
            self.x=nx;self.y=ny
        self.facing=math.atan2(dy,dx);self.moving=True;self.anim+=dt*8
        return False

    def update_ai(self,dt,world,buildings,res):
        self.fire_t=max(0,self.fire_t-dt)
        if self.task is None or self.task=="idle":
            self.task_t-=dt
            if self.task_t<=0: self._pick(world,buildings)
            return
        if self.task=="collect":
            if self.target and self._moveto(self.target[0],self.target[1],dt,world):
                k=(int(self.target[0]//TILE),int(self.target[1]//TILE))
                if k in world.objs and self.total_carry()<5:
                    ob=world.objs[k]
                    if ob in("scrap","ore"):
                        self.carry[ob]=self.carry.get(ob,0)+1;del world.objs[k]
                self.task=None
                if self.total_carry()>=5: self.task="deliver";self._findst(buildings)
        elif self.task=="deliver":
            if not self.target: self._findst(buildings)
            if self.target and self._moveto(self.target[0],self.target[1],dt,world):
                for r,a in self.carry.items(): res[r]=res.get(r,0)+a
                self.carry={};self.task=None

    def _pick(self,world,buildings):
        if self.total_carry()>=5: self.task="deliver";self._findst(buildings);return
        best=None;bd=9999
        for(tx,ty),ob in world.objs.items():
            if ob in("scrap","ore"):
                wx=tx*TILE+TILE//2;wy=ty*TILE+TILE//2
                dd=d2((self.x,self.y),(wx,wy))
                if dd<bd: bd=dd;best=(wx,wy)
        if best: self.target=best;self.task="collect"
        else: self.task="idle";self.task_t=3.0

    def _findst(self,buildings):
        best=None;bd=9999
        for b in buildings:
            if b.btype==B_STORAGE:
                wx=b.tx*TILE+b.sw*TILE//2;wy=b.ty*TILE+b.sh*TILE//2
                dd=d2((self.x,self.y),(wx,wy))
                if dd<bd: bd=dd;best=(wx,wy)
        self.target=best

class Pirate:
    def __init__(self,x,y):
        self.x=float(x);self.y=float(y);self.hp=60;self.max_hp=60
        self.speed=55;self.alive=True;self.atk_t=0.0
    def draw(self,surf,cx,cy,night):
        nm=C_NIGHT;sx=int(self.x-cx);sy=int(self.y-cy)
        if sx<-40 or sy<-40 or sx>SW+40 or sy>SH+40: return
        c=lc((185,20,20),nm,night)
        pygame.draw.ellipse(surf,c,(sx-7,sy-2,14,16))
        pygame.draw.circle(surf,lc((120,10,10),nm,night),(sx,sy-10),8)
        pygame.draw.rect(surf,lc((30,0,0),nm,night),(sx-6,sy-14,12,5),border_radius=1)
        pygame.draw.line(surf,lc((200,0,0),nm,night),(sx-5,sy-12),(sx+5,sy-12),1)
        hw=int(16*self.hp/self.max_hp)
        pygame.draw.rect(surf,(60,0,0),(sx-8,sy-22,16,3))
        pygame.draw.rect(surf,lc(C_DANGER,nm,night),(sx-8,sy-22,hw,3))
    def update(self,dt,tx,ty,buildings,bullets_out):
        dx=tx-self.x;dy=ty-self.y;dd=math.hypot(dx,dy)
        if dd>24:
            self.x+=dx/dd*self.speed*dt;self.y+=dy/dd*self.speed*dt
        else:
            self.atk_t-=dt
            if self.atk_t<=0:
                self.atk_t=1.8
                for b in buildings:
                    bx=b.tx*TILE+b.sw*TILE//2;by=b.ty*TILE+b.sh*TILE//2
                    if d2((self.x,self.y),(bx,by))<70:
                        b.hp=max(0,b.hp-10);break
                bullets_out.append(Bullet(self.x,self.y,tx,ty,"pirate",8))

class Bullet:
    def __init__(self,x,y,tx,ty,owner="player",dmg=15,is_gojo=False):
        self.x=float(x);self.y=float(y)
        dx=tx-x;dy=ty-y;dd=math.hypot(dx,dy) or 1
        self.vx=dx/dd*420;self.vy=dy/dd*420
        self.owner=owner;self.dmg=dmg;self.alive=True;self.life=2.5
        self.is_gojo=is_gojo
        self.col=random.choice([C_GP,C_GB,C_GR]) if is_gojo else(C_GREEN if owner=="player" else C_DANGER)
    def update(self,dt):
        self.x+=self.vx*dt;self.y+=self.vy*dt;self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,cx,cy):
        sx=int(self.x-cx);sy=int(self.y-cy)
        if sx<-10 or sy<-10 or sx>SW+10 or sy>SH+10: return
        c=self.col
        if self.is_gojo:
            pygame.draw.circle(surf,c,(sx,sy),4)
            gs2=pygame.Surface((10,10),pygame.SRCALPHA);gs2.fill((c[0],c[1],c[2],80));surf.blit(gs2,(sx-5,sy-5))
        else:
            pygame.draw.circle(surf,c,(sx,sy),3)

class Particle:
    def __init__(self,x,y,col):
        self.x=float(x);self.y=float(y)
        a=random.uniform(0,math.pi*2);s=random.uniform(50,150)
        self.vx=math.cos(a)*s;self.vy=math.sin(a)*s
        self.life=random.uniform(0.25,0.65);self.ml=self.life;self.col=sc(col);self.alive=True
    def update(self,dt):
        self.x+=self.vx*dt;self.y+=self.vy*dt;self.vx*=0.92;self.vy*=0.92
        self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,cx,cy):
        t=self.life/self.ml;c=lc((0,0,0),self.col,t)
        sx=int(self.x-cx);sy=int(self.y-cy)
        pygame.draw.circle(surf,c,(sx,sy),max(1,int(3*t)))

class Joystick:
    def __init__(self,cx,cy,r=55,inner=22):
        self.cx=cx;self.cy=cy;self.r=r;self.ir=inner
        self.kx=0.0;self.ky=0.0;self.touch_id=None;self.active=False
    def handle(self,ev):
        if ev.type==pygame.FINGERDOWN:
            fx=int(ev.x*SW);fy=int(ev.y*SH)
            if d2((fx,fy),(self.cx,self.cy))<self.r+25:
                self.touch_id=ev.finger_id;self.active=True;self._upd(fx,fy)
        elif ev.type==pygame.FINGERMOTION and ev.finger_id==self.touch_id:
            self._upd(int(ev.x*SW),int(ev.y*SH))
        elif ev.type==pygame.FINGERUP and ev.finger_id==self.touch_id:
            self.touch_id=None;self.active=False;self.kx=0;self.ky=0
    def _upd(self,fx,fy):
        dx=fx-self.cx;dy=fy-self.cy;dd=math.hypot(dx,dy)
        if dd>self.r: dx=dx/dd*self.r;dy=dy/dd*self.r
        self.kx=dx/self.r;self.ky=dy/self.r
    def draw(self,surf):
        a=150 if not self.active else 210
        b=pygame.Surface((self.r*2,self.r*2),pygame.SRCALPHA)
        pygame.draw.circle(b,(0,100,200,a//2),(self.r,self.r),self.r)
        pygame.draw.circle(b,(0,180,255,a),(self.r,self.r),self.r,2)
        surf.blit(b,(self.cx-self.r,self.cy-self.r))
        ix=int(self.cx+self.kx*self.r);iy=int(self.cy+self.ky*self.r)
        kb=pygame.Surface((self.ir*2,self.ir*2),pygame.SRCALPHA)
        pygame.draw.circle(kb,(0,200,255,a+30),(self.ir,self.ir),self.ir)
        pygame.draw.circle(kb,(150,230,255,200),(self.ir,self.ir),self.ir//2)
        surf.blit(kb,(ix-self.ir,iy-self.ir))

class MPClient:
    PORT=25565
    def __init__(self):
        self.sock=None;self.addr=None;self.peers={};self.running=False
        self.is_host=False;self.thread=None
    def host(self):
        try:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.sock.bind(("",self.PORT));self.sock.settimeout(0.05)
            self.is_host=True;self.running=True
            self.thread=threading.Thread(target=self._recv,daemon=True);self.thread.start()
            return True
        except: return False
    def join(self,ip):
        try:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sock.settimeout(0.05);self.addr=(ip,self.PORT);self.running=True
            self.thread=threading.Thread(target=self._recv,daemon=True);self.thread.start()
            return True
        except: return False
    def _recv(self):
        while self.running:
            try:
                data,addr=self.sock.recvfrom(256)
                msg=json.loads(data.decode())
                self.peers[str(addr)]=(msg.get("x",0),msg.get("y",0),
                    msg.get("col",[0,180,255]),msg.get("name","?"),
                    msg.get("facing",0),msg.get("hg","none"))
                if self.is_host:
                    for a2 in list(self.peers):
                        try:
                            parts=a2.strip("()").replace("'","").split(",")
                            self.sock.sendto(data,(parts[0].strip(),self.PORT))
                        except: pass
            except: pass
    def send(self,pl):
        if not self.running or not self.sock: return
        msg={"x":pl.x,"y":pl.y,"col":list(pl.color),"name":pl.name,"facing":pl.facing,"hg":pl.headgear}
        data=json.dumps(msg).encode()
        try:
            if self.is_host:
                for a2 in list(self.peers):
                    try:
                        parts=a2.strip("()").replace("'","").split(",")
                        self.sock.sendto(data,(parts[0].strip(),self.PORT))
                    except: pass
            elif self.addr: self.sock.sendto(data,self.addr)
        except: pass
    def stop(self):
        self.running=False
        if self.sock:
            try: self.sock.close()
            except: pass
    @property
    def connected(self): return self.running and (len(self.peers)>0 or self.is_host)

class GS:
    def __init__(self,pl_color,pl_hg,pl_name="Космонавт"):
        self.stage=1
        self.res={"scrap":10,"ore":0,"crystal":0,"credits":500}
        self.buildings=[];self.npcs=[];self.pirates=[]
        self.bullets=[];self.particles=[];self.fleet=[]
        self.world=World(80,55,TR_SAND)
        self.cam_x=0;self.cam_y=0
        self.player=Character(20*TILE,20*TILE,pl_color,pl_name,is_player=True)
        self.player.headgear=pl_hg;self.pl_color=pl_color;self.pl_hg=pl_hg;self.pl_name=pl_name
        self.day_time=0.0;self.day_speed=0.004
        self.hq_built=False;self.drill_built=False;self.storage_count=0
        self.sonnet_done=False;self.sonnet_t=0.0;self.population=1
        self.raid_triggered=False;self.raid_active=False;self.raid_wave=0
        self.vega_hp=0;self.vega_max=200;self.vega_x=38*TILE;self.vega_y=18*TILE
        self.game_won=False;self.game_over=False
        self.build_type=None;self.msgs=[];self.cur_msg="";self.msg_t=0.0;self.log=[]
        self.inventory=[];self.has_armory=False;self.colony_unlocked=False
        self.in_space=False;self.sp_cam_x=0.0;self.sp_cam_y=0.0
        self.planet_pos={"Вега":(400,300),"Арктус":(1200,200),"Минерва":(800,900),"Юнион-1":(1600,600)}
        self.pb_hp=500;self.pb_pos=(2000,400);self.nova_built=False;self.watchdog=0.0
        self.push("Добро пожаловать на Вегу! Собирайте ресурсы, постройте Штаб.")
    def push(self,m):
        self.msgs.append(m);self.log.append(m)
        if len(self.log)>60: self.log.pop(0)
    def sparks(self,x,y,col,n=8):
        for _ in range(n): self.particles.append(Particle(x,y,col))
    def day_alpha(self): return cl(math.sin(self.day_time*math.pi)*0.7,0.0,1.0)
    def can_afford(self,bt):
        for r,a in BDATA[bt]["cost"].items():
            if self.res.get(r,0)<a: return False
        return True
    def spend(self,bt):
        for r,a in BDATA[bt]["cost"].items(): self.res[r]-=a
    def place(self,tx,ty):
        bt=self.build_type
        if bt is None: return False
        d=BDATA[bt];sw2,sh2=d["size"]
        for b in self.buildings:
            if abs(b.tx-tx)<b.sw+sw2 and abs(b.ty-ty)<b.sh+sh2:
                self.push("Место занято!"); return False
        if not self.can_afford(bt): self.push("Не хватает ресурсов!"); return False
        self.spend(bt);b=Building(bt,tx,ty);self.buildings.append(b);self._on_build(b);return True
    def _on_build(self,b):
        if b.btype==B_HQ: self.hq_built=True;self.push("Штаб построен! Постройте Бур и Оружейную.")
        elif b.btype==B_DRILL: self.drill_built=True;self.push("Бур запущен!")
        elif b.btype==B_ARMORY:
            self.has_armory=True;self.player.weapon="pistol"
            self.push("Оружейная! Получен пистолет.");self.inventory.append("Пистолет")
        elif b.btype==B_STORAGE:
            self.storage_count+=1
            if self.storage_count>=2 and not self.sonnet_done:
                self.sonnet_done=True;self.sonnet_t=5.0;self.push("СИГНАЛ! Корабль входит в атмосферу!")
        elif b.btype==B_ASSEMBLY: self.stage=max(self.stage,2);self.push("Сборщик ТС готов!")
        elif b.btype in(B_HOUSE,B_BARRACKS):
            add=5 if b.btype==B_HOUSE else 8;self.population+=add
            self.push(f"Нас: +{add} = {self.population}")
            if self.population>=10: self.colony_unlocked=True
            if self.population>=30 and not self.raid_triggered:
                self.raid_triggered=True;self.raid_active=True;self.push("!! АТАКА ПИРАТОВ !!")
                self._spawn_raid()
        elif b.btype==B_SHIPYARD:
            self.stage=max(self.stage,3);self.inventory.append("Чертёж: Нова");self.push("Верфь готова!")
    def _spawn_raid(self):
        for _ in range(5+self.raid_wave*2):
            self.pirates.append(Pirate(random.randint(0,self.world.w-1)*TILE,random.randint(0,self.world.h-1)*TILE))
        self.raid_wave+=1
    def spawn_sonnet(self):
        cx=self.world.w//2*TILE;cy=self.world.h//2*TILE;self.sparks(cx,cy,(255,200,0),30)
        ph=self.pl_color
        for i,nm in enumerate(["Алекс","Мира","Карл"]):
            for _ in range(30):
                c=(random.randint(40,220),random.randint(40,220),random.randint(40,220))
                if abs(c[0]-ph[0])>40 or abs(c[1]-ph[1])>40 or abs(c[2]-ph[2])>40: break
            npc=Character(cx+i*TILE*2,cy,sc(c),nm)
            npc.headgear=random.choice(HG_LIST[:5]);self.npcs.append(npc)
        self.stage=max(self.stage,2);self.population+=3
        self.inventory.append("Бортжурнал: Соннет");self.push("'Соннет' сел! 3 выживших присоединились.")
    def save(self,slot=0):
        try:
            d={"res":self.res,"stage":self.stage,"pop":self.population,
               "vega_hp":self.vega_hp,"pl_color":list(self.pl_color),
               "pl_hg":self.pl_hg,"pl_name":self.pl_name,"inventory":self.inventory,"log":self.log[-20:]}
            with open(f"nova_save_{slot}.json","w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False)
            self.push("Игра сохранена!")
        except Exception as e: self.push(f"Ошибка: {e}")
    @staticmethod
    def load_info(slot=0):
        fn=f"nova_save_{slot}.json"
        if not os.path.exists(fn): return None
        try:
            with open(fn,"r",encoding="utf-8") as f: return json.load(f)
        except: return None

class TabletUI:
    def __init__(self):
        self.open=False;self.tab="main";self.anim=0.0
    def toggle(self): self.open=not self.open;self.tab="main"
    def draw(self,surf,gs):
        if not self.open: return
        self.anim=min(1.0,self.anim+0.1)
        pw=int(SW*0.70*self.anim);ph=int(SH*0.80)
        px=(SW-pw)//2;py=(SH-ph)//2
        if pw<20: return
        bg=pygame.Surface((pw,ph),pygame.SRCALPHA);bg.fill((4,14,32,235));surf.blit(bg,(px,py))
        pygame.draw.rect(surf,C_FRAME,(px,py,pw,ph),2,border_radius=8)
        pygame.draw.rect(surf,(0,60,120),(px,py,pw,24),border_radius=8)
        txt(surf,"== ПЛАНШЕТ NOVA ==",(px+pw//2,py+4),FM,C_FRAME,center=True)
        for cx2,cy2,a in[(px+4,py+4,0),(px+pw-4,py+4,math.pi/2),(px+4,py+ph-4,math.pi*1.5),(px+pw-4,py+ph-4,math.pi)]:
            pygame.draw.arc(surf,C_FRAME,(cx2-8,cy2-8,16,16),a,a+math.pi/2,2)
        tabs=[("main","Главная"),("inv","Инвентарь"),("build","Строить"),("planet","Планета")]
        if gs.colony_unlocked: tabs.append(("colony","Колония"))
        tw=min(105,(pw-16)//len(tabs))
        self._tabs_rects=[]
        for i,(tid,tlbl) in enumerate(tabs):
            r=pygame.Rect(px+8+i*(tw+3),py+26,tw,22)
            self._tabs_rects.append((r,tid))
            dbtn(surf,r,tlbl,active=(self.tab==tid),hover=r.collidepoint(pygame.mouse.get_pos()),font=FS)
        cy3=py+54;cx3=px+10
        if self.tab=="main":    self._tmain(surf,gs,cx3,cy3,pw,ph,px,py)
        elif self.tab=="inv":   self._tinv(surf,gs,cx3,cy3,pw)
        elif self.tab=="build": self._tbuild(surf,gs,cx3,cy3,pw)
        elif self.tab=="planet":self._tplanet(surf,gs,cx3,cy3)
        elif self.tab=="colony":self._tcolony(surf,gs,cx3,cy3)
        self._cr=pygame.Rect(px+pw-72,py+ph-28,68,24)
        dbtn(surf,self._cr,"[X] Закрыть",font=FS)

    def _tmain(self,surf,gs,cx,cy,pw,ph,px,py):
        txt(surf,"БЫСТРЫЕ ДЕЙСТВИЯ",(cx,cy),FM,C_FRAME)
        mp=pygame.mouse.get_pos()
        bw=(pw-30)//2;bh=34
        btns_rects=[
            ("Собрать [E]",pygame.Rect(cx,cy+24,bw,bh)),
            ("Бежать",     pygame.Rect(cx+bw+10,cy+24,bw,bh)),
            ("Сохранить",  pygame.Rect(cx,cy+64,bw,bh)),
            ("В КОСМОС",   pygame.Rect(cx+bw+10,cy+64,bw,bh)),
        ]
        self._main_btns_r=btns_rects
        for lbl,r in btns_rects:
            dbtn(surf,r,lbl,hover=r.collidepoint(mp),font=FS)
        txt(surf,"Ресурсы:",(cx,cy+106),FM,C_TEXT2)
        for i,(k,v) in enumerate(gs.res.items()):
            txt(surf,f"{k}:{v}",(cx+i*(pw//4),cy+126),FS,C_TEXT)

    def _tinv(self,surf,gs,cx,cy,pw):
        txt(surf,"ИНВЕНТАРЬ",(cx,cy),FM,C_FRAME);y=cy+24
        for it in gs.inventory: txt(surf,f"- {it}",(cx,y),FS,C_TEXT);y+=20
        if not gs.inventory: txt(surf,"Пусто",(cx,y),FS,C_TEXT2)
        txt(surf,"ЖУРНАЛ:",(cx,cy+140),FM,C_TEXT2)
        for i,e in enumerate(gs.log[-12:]):
            a=max(80,200-(12-i)*10);txt(surf,e[:46],(cx,cy+160+i*18),FS,sc((a//2,a,a)))

    def _tbuild(self,surf,gs,cx,cy,pw):
        txt(surf,"СТРОИТЕЛЬСТВО",(cx,cy),FM,C_FRAME)
        avail=[]
        if not gs.hq_built: avail.append(B_HQ)
        elif not gs.drill_built: avail.append(B_DRILL)
        else:
            avail+=[B_STORAGE,B_ARMORY,B_HOUSE]
            if gs.stage>=2: avail+=[B_STUDY,B_ASSEMBLY,B_BARRACKS]
            if any(b.btype==B_ASSEMBLY for b in gs.buildings): avail.append(B_SHIPYARD)
        mp=pygame.mouse.get_pos();bw=(pw-28)//2;bh=46
        self._build_rects=[]
        for i,bt in enumerate(avail):
            d=BDATA[bt];col2=i%2;row2=i//2
            r=pygame.Rect(cx+col2*(bw+8),cy+24+row2*(bh+6),bw,bh)
            self._build_rects.append((r,bt))
            can=gs.can_afford(bt);active=(gs.build_type==bt)
            dbtn(surf,r,d["name"],active=active,hover=r.collidepoint(mp),font=FS)
            cs=" ".join(f"{v}{k[:2]}" for k,v in d["cost"].items())
            txt(surf,cs,(r.x+4,r.y+r.h-16),FS,C_GREEN if can else C_DANGER)

    def _tplanet(self,surf,gs,cx,cy):
        txt(surf,"ПЛАНЕТА ВЕГА",(cx,cy),FM,C_FRAME)
        info=[("Тип","Пустынная/Камень"),("Гравитация","0.82 G"),("CO2+N","Фильтр обяз."),
              ("Темп.","от -20 до +55 C"),("Ресурсы","Лом, Руда"),("Опасн.","Пиратские рейды"),
              ("Этап",{1:"Выживание",2:"Колония",3:"Космос"}.get(gs.stage,"?"))]
        for i,(k,v) in enumerate(info):
            txt(surf,f"{k}:",(cx,cy+24+i*22),FS,C_TEXT2);txt(surf,str(v),(cx+155,cy+24+i*22),FS,C_TEXT)

    def _tcolony(self,surf,gs,cx,cy):
        txt(surf,"КОЛОНИЯ",(cx,cy),FM,C_FRAME)
        items=[("Население",gs.population),("Постройки",len(gs.buildings)),
               ("NPC",len(gs.npcs)),("Лом",gs.res.get("scrap",0)),("Руда",gs.res.get("ore",0)),
               ("Флот",str(len(gs.fleet))+" кор."),("Вега HP",f"{gs.vega_hp}/{gs.vega_max}"),("Рейд волна",gs.raid_wave)]
        for i,(k,v) in enumerate(items):
            txt(surf,f"{k}:",(cx,cy+24+i*22),FS,C_TEXT2);txt(surf,str(v),(cx+180,cy+24+i*22),FS,C_TEXT)

    def handle_click(self,pos,gs):
        if not self.open: return False
        if hasattr(self,"_cr") and self._cr.collidepoint(pos): self.open=False;return True
        if hasattr(self,"_tabs_rects"):
            for r,tid in self._tabs_rects:
                if r.collidepoint(pos): self.tab=tid;return True
        if self.tab=="main" and hasattr(self,"_main_btns_r"):
            for lbl,r in self._main_btns_r:
                if r.collidepoint(pos):
                    if lbl=="Сохранить": gs.save()
                    elif lbl=="В КОСМОС":
                        if gs.stage>=3 and gs.vega_hp>=gs.vega_max:
                            gs.in_space=True;gs.push("Взлёт!");self.open=False
                        else: gs.push("'Вега' не готова.")
                    return True
        if self.tab=="build" and hasattr(self,"_build_rects"):
            for r,bt in self._build_rects:
                if r.collidepoint(pos) and gs.can_afford(bt):
                    gs.build_type=bt;self.open=False;return True
        return True

class MainMenu:
    def __init__(self):
        self.ss="main";self.pl_hue=210;self.hg_idx=0;self.pl_name="Космонавт"
        self.ne=False;self.anim=0.0;self.mp_ip="";self.mp_ip_e=False
    def color(self):
        import colorsys;r,g,b=colorsys.hsv_to_rgb(self.pl_hue/360,0.88,0.9)
        return sc((int(r*255),int(g*255),int(b*255)))
    def headgear(self): return HG_LIST[self.hg_idx]
    def update(self,dt): self.anim+=dt
    def handle(self,ev,si):
        pos=None
        if ev.type==pygame.FINGERDOWN: pos=(int(ev.x*SW),int(ev.y*SH))
        elif ev.type==pygame.MOUSEBUTTONDOWN: pos=ev.pos
        if pos:
            if self.ss=="main":   return self._mev(pos,si)
            if self.ss=="settings": self._sev(pos)
            if self.ss=="mp":     return self._mpev(pos)
        if ev.type==pygame.KEYDOWN:
            if self.ne:
                if ev.key==pygame.K_RETURN:
                    self.ne=False; pygame.key.stop_text_input()
                elif ev.key==pygame.K_BACKSPACE:
                    self.pl_name=self.pl_name[:-1]
                elif ev.unicode and len(self.pl_name)<12:
                    self.pl_name+=ev.unicode
            if self.mp_ip_e:
                if ev.key==pygame.K_RETURN: self.mp_ip_e=False; pygame.key.stop_text_input()
                elif ev.key==pygame.K_BACKSPACE: self.mp_ip=self.mp_ip[:-1]
                elif ev.unicode and len(self.mp_ip)<16 and(ev.unicode.isdigit() or ev.unicode=="."): self.mp_ip+=ev.unicode
        # TEXTINPUT — основной способ ввода текста на Android
        if ev.type==pygame.TEXTINPUT:
            if self.ne and len(self.pl_name)<12:
                self.pl_name+=ev.text
            if self.mp_ip_e and len(self.mp_ip)<16:
                for ch in ev.text:
                    if ch.isdigit() or ch==".": self.mp_ip+=ch
        return None
    def _mev(self,pos,si):
        bx=SW//2-us(110);by=SH//2-us(40)
        bw=us(220);bh=us(50);gap=us(60)
        btns=[("play",pygame.Rect(bx,by,bw,bh)),
              ("settings",pygame.Rect(bx,by+gap,bw,bh)),
              ("mp",pygame.Rect(bx,by+gap*2,bw,bh))]
        if si: btns.append(("load",pygame.Rect(bx,by+gap*3,bw,bh)))
        for act,r in btns:
            if r.collidepoint(pos): return act
        return None
    def _sev(self,pos):
        cx=SW//2; cy=SH//2
        bw=us(44); bh=us(36); hoff=us(90); roff=us(54)
        if pygame.Rect(cx-hoff,cy-us(30),bw,bh).collidepoint(pos): self.pl_hue=(self.pl_hue-20)%360
        if pygame.Rect(cx+roff,cy-us(30),bw,bh).collidepoint(pos): self.pl_hue=(self.pl_hue+20)%360
        if pygame.Rect(cx-hoff,cy+us(22),bw,bh).collidepoint(pos): self.hg_idx=(self.hg_idx-1)%len(HG_LIST)
        if pygame.Rect(cx+roff,cy+us(22),bw,bh).collidepoint(pos): self.hg_idx=(self.hg_idx+1)%len(HG_LIST)
        nr=pygame.Rect(cx-us(10),cy+us(68),us(170),us(32))
        if nr.collidepoint(pos):
            self.ne=True
            pygame.key.start_text_input()
        back_r=pygame.Rect(cx-us(65),cy+us(115),us(130),us(38))
        if back_r.collidepoint(pos):
            self.ss="main"; pygame.key.stop_text_input(); self.ne=False
    def _mpev(self,pos):
        cx=SW//2
        if pygame.Rect(cx-80,SH//2-14,160,36).collidepoint(pos): return("mp","host",None)
        if pygame.Rect(cx-100,SH//2+48,200,30).collidepoint(pos): self.mp_ip_e=True
        if pygame.Rect(cx-50,SH//2+82,100,30).collidepoint(pos) and self.mp_ip: return("mp","join",self.mp_ip)
        if pygame.Rect(cx-50,SH//2+122,100,30).collidepoint(pos): self.ss="main"
        return None
    def draw(self,surf,si):
        surf.fill(C_BG)
        for x in range(0,SW,44): pygame.draw.line(surf,C_GRID,(x,0),(x,SH))
        for y in range(0,SH,44): pygame.draw.line(surf,C_GRID,(0,y),(SW,y))
        rng=random.Random(42);t=self.anim
        for _ in range(100):
            sx=rng.randint(0,SW);sy=rng.randint(0,SH//2);br=int(80+abs(math.sin(t+rng.random()*6))*170)
            pygame.draw.circle(surf,(br,br,br),(sx,sy),rng.randint(1,2))
        if self.ss=="main":     self._dmain(surf,si)
        elif self.ss=="settings": self._dsett(surf)
        elif self.ss=="mp":     self._dmp(surf)
    def _dmain(self,surf,si):
        gl=int(abs(math.sin(self.anim))*80)
        txt(surf,"== NOVA FRONTIER ==",(SW//2,SH//2-us(175)),FXL,sc((0,180+gl,255)),center=True,shadow=True)
        txt(surf,"Выживание на краю галактики",(SW//2,SH//2-us(130)),FM,C_TEXT2,center=True)
        mp=pygame.mouse.get_pos()
        bx=SW//2-us(110); by=SH//2-us(40); bw=us(220); bh=us(50); gap=us(60)
        btns=[(">> ИГРАТЬ <<",pygame.Rect(bx,by,bw,bh)),
              ("НАСТРОЙКИ",   pygame.Rect(bx,by+gap,bw,bh)),
              ("МУЛЬТИПЛЕЕР", pygame.Rect(bx,by+gap*2,bw,bh))]
        if si: btns.append(("ЗАГРУЗИТЬ",pygame.Rect(bx,by+gap*3,bw,bh)))
        for lbl,r in btns: dbtn(surf,r,lbl,active=(lbl==">> ИГРАТЬ <<"),hover=r.collidepoint(mp),font=FM)
        txt(surf,"v3.0 | Android | Pydroid3",(SW//2,SH-us(18)),FS,C_DIM,center=True)
    def _dsett(self,surf):
        cx=SW//2; cy=SH//2
        pw=us(440); ph=us(300)
        dpanel(surf,(cx-pw//2,cy-ph//2,pw,ph))
        txt(surf,"НАСТРОЙКИ ПЕРСОНАЖА",(cx,cy-ph//2+us(10)),FM,C_FRAME,center=True)
        pc=self.color(); mp=pygame.mouse.get_pos()
        bw=us(46); bh=us(38); hoff=us(92); roff=us(56)
        # Цвет
        txt(surf,"Цвет скафандра:",(cx-pw//2+us(14),cy-us(28)),FM,C_TEXT2)
        pygame.draw.rect(surf,pc,(cx-us(10),cy-us(36),us(52),us(38)))
        pygame.draw.rect(surf,C_FRAME,(cx-us(10),cy-us(36),us(52),us(38)),2)
        for r,lbl in [(pygame.Rect(cx-hoff,cy-us(32),bw,bh),"<"),(pygame.Rect(cx+roff,cy-us(32),bw,bh),">")]:
            dbtn(surf,r,lbl,hover=r.collidepoint(mp),font=FM)
        # Прибор
        txt(surf,"Прибор:",(cx-pw//2+us(14),cy+us(24)),FM,C_TEXT2)
        txt(surf,HG_NAMES.get(self.headgear(),"?"),(cx+us(6),cy+us(24)),FM,C_TEXT)
        for r,lbl in [(pygame.Rect(cx-hoff,cy+us(20),bw,bh),"<"),(pygame.Rect(cx+roff,cy+us(20),bw,bh),">")]:
            dbtn(surf,r,lbl,hover=r.collidepoint(mp),font=FM)
        # Имя
        txt(surf,"Имя космонавта:",(cx-pw//2+us(14),cy+us(76)),FM,C_TEXT2)
        nr=pygame.Rect(cx-us(12),cy+us(70),us(185),us(34))
        pygame.draw.rect(surf,(0,30,60),nr,border_radius=4)
        pygame.draw.rect(surf,C_FRAME if self.ne else C_DIM,nr,2,border_radius=4)
        txt(surf,self.pl_name+("_" if self.ne else ""),(cx-us(8),cy+us(74)),FM,C_TEXT)
        if self.ne:
            txt(surf,"(нажмите Enter чтобы закончить)",(cx,cy+us(108)),FS,C_TEXT2,center=True)
        else:
            txt(surf,"(нажмите чтобы изменить)",(cx,cy+us(108)),FS,C_DIM,center=True)
        # Превью персонажа
        self._prev(surf,cx+us(195),cy+us(10))
        # Назад
        back_r=pygame.Rect(cx-us(68),cy+us(120),us(136),us(40))
        dbtn(surf,back_r,"<< Назад",hover=back_r.collidepoint(mp),font=FM)
    def _dmp(self,surf):
        cx=SW//2;dpanel(surf,(cx-220,SH//2-90,440,250))
        txt(surf,"МУЛЬТИПЛЕЕР (LAN)",(cx,SH//2-82),FM,C_FRAME,center=True)
        mp2=pygame.mouse.get_pos()
        txt(surf,"Создать хост:",(cx-200,SH//2-30),FS,C_TEXT2)
        hr=pygame.Rect(cx-80,SH//2-14,160,36);dbtn(surf,hr,"СОЗДАТЬ ИГРУ",hover=hr.collidepoint(mp2))
        txt(surf,"Подключиться:",(cx-200,SH//2+30),FS,C_TEXT2)
        ir=pygame.Rect(cx-100,SH//2+48,200,30)
        pygame.draw.rect(surf,(0,20,50),ir,border_radius=4)
        pygame.draw.rect(surf,C_FRAME if self.mp_ip_e else C_DIM,ir,2,border_radius=4)
        txt(surf,(self.mp_ip or "IP адрес..."),(cx-96,SH//2+52),FS,C_TEXT)
        jr=pygame.Rect(cx-50,SH//2+82,100,30);dbtn(surf,jr,"ВОЙТИ",hover=jr.collidepoint(mp2))
        br=pygame.Rect(cx-50,SH//2+122,100,30);dbtn(surf,br,"Назад",hover=br.collidepoint(mp2))
    def _prev(self,surf,cx,cy):
        c=self.color()
        pygame.draw.rect(surf,c,(cx-8,cy-2,16,14),border_radius=3)
        pygame.draw.rect(surf,(15,15,25),(cx-3,cy+11,6,10))
        pygame.draw.ellipse(surf,(210,200,190),(cx-8,cy-20,16,14))
        hg=self.headgear()
        if hg=="helmet": pygame.draw.ellipse(surf,(60,80,120),(cx-9,cy-28,18,14))
        elif hg=="visor": pygame.draw.rect(surf,(0,80,180),(cx-8,cy-22,16,6),border_radius=2)
        elif hg=="antenna": pygame.draw.line(surf,C_WARN,(cx,cy-20),(cx+5,cy-30),2);pygame.draw.circle(surf,C_WARN,(cx+5,cy-30),3)
        elif hg=="goggles":
            for ox in[-4,4]: pygame.draw.circle(surf,(0,180,255),(cx+ox,cy-14),4,1)
        elif hg=="sixeyes":
            for i in range(-8,10,3): pygame.draw.line(surf,(240,240,245),(cx+i,cy-20),(cx+i,cy-28),2)
            pygame.draw.rect(surf,(15,15,20),(cx-9,cy-20,18,5))

class SpaceScreen:
    def draw(self,surf,gs):
        surf.fill((2,4,14));rng=random.Random(55)
        for _ in range(180):
            sx=rng.randint(0,SW);sy=rng.randint(0,SH);br=rng.randint(50,220)
            pygame.draw.circle(surf,(br,br,br),(sx,sy),1)
        PCols={"Вега":(180,140,60),"Арктус":(160,200,230),"Минерва":(120,80,160),"Юнион-1":(80,160,80)}
        cx=int(gs.sp_cam_x);cy=int(gs.sp_cam_y)
        for nm,(wx,wy) in gs.planet_pos.items():
            sx2=wx-cx+SW//2;sy2=wy-cy+SH//2
            if -60<sx2<SW+60 and -60<sy2<SH+60:
                r=30 if "Юнион" not in nm else 18;c=PCols.get(nm,(100,100,100))
                pygame.draw.circle(surf,c,(int(sx2),int(sy2)),r)
                pygame.draw.circle(surf,C_FRAME,(int(sx2),int(sy2)),r,2)
                txt(surf,nm,(int(sx2),int(sy2)+r+5),FS,C_TEXT,center=True)
        pbx=gs.pb_pos[0]-cx+SW//2;pby=gs.pb_pos[1]-cy+SH//2
        if -30<pbx<SW+30 and -30<pby<SH+30:
            pygame.draw.polygon(surf,C_DANGER,[(pbx,pby-14),(pbx+14,pby+10),(pbx-14,pby+10)])
            pygame.draw.polygon(surf,C_DANGER,[(pbx,pby-14),(pbx+14,pby+10),(pbx-14,pby+10)],2)
            txt(surf,"База пиратов",(pbx,pby+14),FS,C_DANGER,center=True)
            pct=gs.pb_hp/500;pygame.draw.rect(surf,(50,0,0),(pbx-30,pby-22,60,5))
            pygame.draw.rect(surf,C_DANGER,(pbx-30,pby-22,int(60*pct),5))
        px2=SW//2;py2=SH//2
        pygame.draw.polygon(surf,sc(gs.pl_color),[(px2,py2-16),(px2+10,py2+8),(px2-10,py2+8)])
        pygame.draw.polygon(surf,C_FRAME,[(px2,py2-16),(px2+10,py2+8),(px2-10,py2+8)],2)
        txt(surf,"[Вега]",(px2,py2+12),FS,C_TEXT,center=True)
        for i,nm2 in enumerate(gs.fleet):
            fx=px2+(i+1)*30;pygame.draw.polygon(surf,C_FRAME,[(fx,py2-10),(fx+7,py2+5),(fx-7,py2+5)])
        for b in gs.bullets: b.draw(surf,cx-SW//2,cy-SH//2)
        dpanel(surf,(4,4,320,36));txt(surf,f"КОСМОС | База: {gs.pb_hp}/500 HP",(8,8),FS,C_FRAME)
        txt(surf,f"Флот: {len(gs.fleet)+1} корабль",(8,22),FS,C_TEXT)
        txt(surf,"Лев.джой-полёт  Прав.джой-огонь  ESC-назад",(SW//2,SH-16),FS,C_TEXT2,center=True)

class ResultScreen:
    def draw(self,surf,won):
        surf.fill(C_BG)
        for x in range(0,SW,44): pygame.draw.line(surf,C_GRID,(x,0),(x,SH))
        for y in range(0,SH,44): pygame.draw.line(surf,C_GRID,(0,y),(SW,y))
        if won:
            txt(surf,"== ПОБЕДА ==",(SW//2,SH//2-80),FXL,C_GREEN,center=True,shadow=True)
            txt(surf,"База пиратов уничтожена!",(SW//2,SH//2-30),FL,C_TEXT,center=True)
        else:
            txt(surf,"== ПРОВАЛ ==",(SW//2,SH//2-80),FXL,C_DANGER,center=True,shadow=True)
            txt(surf,"Штаб уничтожен.",(SW//2,SH//2-30),FL,C_TEXT,center=True)
        txt(surf,"[R] Новая игра",(SW//2,SH//2+60),FM,C_TEXT2,center=True)
        txt(surf,"[ESC] Меню",(SW//2,SH//2+92),FM,C_TEXT2,center=True)

class Game:
    def __init__(self):
        self.surf=screen;self.clock=pygame.time.Clock()
        self.menu=MainMenu();self.tablet=TabletUI()
        self.sp_scr=SpaceScreen();self.res_scr=ResultScreen()
        self.gs=None;self.state="menu";self.running=True
        jr=us(58); jir=us(23)
        jy=SH-us(76)
        self.joy_move=Joystick(us(82),jy,r=jr,inner=jir)
        self.joy_aim=Joystick(SW-us(82),jy,r=jr,inner=jir)
        self.mp=MPClient();self.mp_t=0.0
        bth=us(32); btw=us(100)
        self.btn_tab=pygame.Rect(SW//2-btw//2,us(5),btw,bth)
        self.btn_run=pygame.Rect(SW-us(170),SH-us(108),us(78),bth)
        self.btn_pick=pygame.Rect(SW-us(170),SH-us(70),us(78),bth)
        self.run_boost=False

    def new_game(self,data=None):
        self.gs=GS(self.menu.color(),self.menu.headgear(),self.menu.pl_name)
        if data:
            self.gs.res=data.get("res",self.gs.res)
            self.gs.stage=data.get("stage",1)
            self.gs.population=data.get("pop",1)
            self.gs.vega_hp=data.get("vega_hp",0)
            self.gs.inventory=data.get("inventory",[])
            self.gs.log=data.get("log",[])
            self.gs.push("Игра загружена!")
        self.tablet.open=False;self.state="game"

    def run(self):
        while self.running:
            dt=self.clock.tick(FPS)/1000.0;dt=min(dt,0.1)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: self.running=False
                self._handle(ev)
            self._update(dt);self._draw();pygame.display.flip()
        self.mp.stop();pygame.quit();sys.exit()

    def _handle(self,ev):
        self.joy_move.handle(ev);self.joy_aim.handle(ev)
        if self.state=="menu":
            si=GS.load_info();r=self.menu.handle(ev,si)
            if r=="play":    self.new_game()
            elif r=="settings": self.menu.ss="settings"
            elif r=="mp":    self.menu.ss="mp"
            elif r=="load" and si: self.new_game(si)
            elif isinstance(r,tuple) and r[0]=="mp":
                mode=r[1];ip=r[2]
                if mode=="host": self.mp.host();self.new_game()
                elif mode=="join": self.mp.join(ip);self.new_game()
            return
        if self.state=="result":
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: self.state="menu"
                if ev.key==pygame.K_r:      self.new_game()
            if ev.type in(pygame.MOUSEBUTTONDOWN,pygame.FINGERDOWN):
                pos=self._fp(ev)
                if pos[1]>SH//2+50: self.new_game()
            return
        gs=self.gs
        if ev.type in(pygame.MOUSEBUTTONDOWN,pygame.FINGERDOWN):
            pos=self._fp(ev)
            if self.btn_tab.collidepoint(pos): self.tablet.toggle();return
            if self.tablet.open: self.tablet.handle_click(pos,gs);return
            if self.btn_run.collidepoint(pos): self.run_boost=not self.run_boost;return
            if self.btn_pick.collidepoint(pos): self._interact(gs);return
            if not gs.in_space and gs.build_type:
                tx=(pos[0]+gs.cam_x)//TILE;ty=(pos[1]+gs.cam_y)//TILE
                if gs.place(tx,ty): gs.build_type=None
                return
        if ev.type==pygame.KEYDOWN:
            k=ev.key
            if k==pygame.K_ESCAPE:
                if gs.in_space: gs.in_space=False
                elif self.tablet.open: self.tablet.open=False
                else: self.state="menu"
            if k==pygame.K_F5: gs.save()
            if k==pygame.K_e:  self._interact(gs)
            if k==pygame.K_m:
                if gs.stage>=3 and gs.vega_hp>=gs.vega_max:
                    gs.in_space=True;gs.push("Взлёт!")
                else: gs.push("'Вега' не готова.")

    def _fp(self,ev):
        if ev.type==pygame.FINGERDOWN: return(int(ev.x*SW),int(ev.y*SH))
        return ev.pos

    def _interact(self,gs):
        px,py=gs.player.x,gs.player.y
        tx2,ty2=int(px//TILE),int(py//TILE)
        # Радиус сбора — 3 тайла во все стороны
        for dx in range(-3,4):
            for dy in range(-3,4):
                k=(tx2+dx,ty2+dy)
                if k in gs.world.objs:
                    ob=gs.world.objs[k]
                    if ob in("scrap","ore"):
                        gs.res[ob]=gs.res.get(ob,0)+2
                        del gs.world.objs[k]
                        wx=k[0]*TILE+TILE//2; wy=k[1]*TILE+TILE//2
                        gs.sparks(wx,wy,C_WARN if ob=="scrap" else C_FRAME,12)
                        gs.push(f"+2 {ob}")
                        return  # собрать один предмет за раз
        # Ремонт Веги — увеличенный радиус
        if d2((px,py),(gs.vega_x,gs.vega_y))<160 and gs.vega_hp<gs.vega_max:
            if gs.res.get("ore",0)>=20:
                gs.res["ore"]-=20
                gs.vega_hp=min(gs.vega_max,gs.vega_hp+50)
                gs.push(f"Вега отремонтирована: {gs.vega_hp}/{gs.vega_max}")
                gs.sparks(gs.vega_x,gs.vega_y,C_GREEN,15)
            else:
                gs.push("Нужно 20 руды для ремонта Веги.")
            return
        gs.push("Рядом нет ресурсов для сбора.")

    def _update(self,dt):
        if self.state!="game" or self.gs is None: return
        gs=self.gs
        if gs.game_won or gs.game_over: self.state="result";return
        fps=self.clock.get_fps()
        gs.watchdog=gs.watchdog+dt if 0<fps<5 else 0
        if gs.watchdog>20: pygame.quit();sys.exit(1)
        if gs.in_space: self._uspace(dt);return
        gs.day_time=(gs.day_time+gs.day_speed*dt)%1.0
        if gs.cur_msg:
            gs.msg_t-=dt
            if gs.msg_t<=0: gs.cur_msg=""
        if not gs.cur_msg and gs.msgs: gs.cur_msg=gs.msgs.pop(0);gs.msg_t=3.5
        gs.player.fire_t=max(0,gs.player.fire_t-dt)
        # Движение
        kx=self.joy_move.kx;ky=self.joy_move.ky
        keys=pygame.key.get_pressed()
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: kx-=1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: kx+=1
        if keys[pygame.K_UP]    or keys[pygame.K_w]: ky-=1
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: ky+=1
        mag=math.hypot(kx,ky);boost=1.7 if self.run_boost else 1.0
        if mag>0.05:
            spd=gs.player.speed*boost
            nx=gs.player.x+kx/mag*spd*dt;ny=gs.player.y+ky/mag*spd*dt
            if gs.world.is_passable(nx,gs.player.y): gs.player.x=nx
            if gs.world.is_passable(gs.player.x,ny): gs.player.y=ny
            gs.player.facing=math.atan2(ky,kx);gs.player.moving=True;gs.player.anim+=dt*8
        else: gs.player.moving=False
        gs.player.x=cl(gs.player.x,0,gs.world.w*TILE-1)
        gs.player.y=cl(gs.player.y,0,gs.world.h*TILE-1)
        # Стрельба правым джойстиком
        ax=self.joy_aim.kx;ay=self.joy_aim.ky;am=math.hypot(ax,ay)
        if am>0.3 and gs.player.weapon!="none" and gs.has_armory:
            gs.player.facing=math.atan2(ay,ax)
            wd=WEAPONS.get(gs.player.weapon)
            if wd and gs.player.fire_t<=0:
                gs.player.fire_t=wd["rate"]
                tx3=gs.player.x+ax*200;ty3=gs.player.y+ay*200
                gs.bullets.append(Bullet(gs.player.x,gs.player.y,tx3,ty3,"player",wd["dmg"],gs.player.headgear=="sixeyes"))
        if keys[pygame.K_SPACE] and gs.player.weapon!="none" and gs.has_armory:
            if gs.player.fire_t<=0:
                wd=WEAPONS.get(gs.player.weapon)
                if wd:
                    gs.player.fire_t=wd["rate"]
                    cos_f=math.cos(gs.player.facing);sin_f=math.sin(gs.player.facing)
                    gs.bullets.append(Bullet(gs.player.x,gs.player.y,gs.player.x+cos_f*300,gs.player.y+sin_f*300,"player",wd["dmg"],gs.player.headgear=="sixeyes"))
        gs.cam_x=cl(int(gs.player.x-SW//2),0,gs.world.w*TILE-SW)
        gs.cam_y=cl(int(gs.player.y-SH//2),0,gs.world.h*TILE-SH)
        for b in gs.buildings: b.update(dt,gs.res)
        for n in gs.npcs: n.update_ai(dt,gs.world,gs.buildings,gs.res)
        if gs.raid_active:
            hq=next((b for b in gs.buildings if b.btype==B_HQ),None)
            tx4=(hq.tx*TILE+TILE) if hq else gs.player.x
            ty4=(hq.ty*TILE+TILE) if hq else gs.player.y
            for p in gs.pirates: p.update(dt,tx4,ty4,gs.buildings,gs.bullets)
            gs.pirates=[p for p in gs.pirates if p.alive and p.hp>0]
            if not gs.pirates:
                gs.raid_active=False;gs.push("Рейд отбит!")
                if gs.vega_hp==0: gs.vega_hp=1;gs.push("Найден 'Вега'! Починить [E] рядом.")
        for b in gs.bullets: b.update(dt)
        for b in gs.bullets:
            if b.owner=="player":
                for p in gs.pirates:
                    if d2((b.x,b.y),(p.x,p.y))<18:
                        p.hp-=b.dmg;b.alive=False
                        if p.hp<=0: p.alive=False;gs.sparks(p.x,p.y,C_DANGER)
                        break
            elif b.owner=="pirate":
                if d2((b.x,b.y),(gs.player.x,gs.player.y))<16:
                    gs.player.hp=max(0,gs.player.hp-b.dmg);b.alive=False
                    if gs.player.hp<=0: gs.game_over=True
        gs.bullets=[b for b in gs.bullets if b.alive]
        for p in gs.particles: p.update(dt)
        gs.particles=[p for p in gs.particles if p.alive]
        if gs.sonnet_done and not any(n.name in("Алекс","Мира","Карл") for n in gs.npcs):
            gs.sonnet_t-=dt
            if gs.sonnet_t<=0: gs.sonnet_done=False;gs.spawn_sonnet()
        dead=[b for b in gs.buildings if b.hp<=0]
        for b in dead:
            gs.sparks(b.tx*TILE,b.ty*TILE,C_DANGER,14);gs.push(f"{b.name} разрушен!")
            if b.btype==B_HQ: gs.game_over=True
        gs.buildings=[b for b in gs.buildings if b.hp>0]
        if self.mp.connected:
            self.mp_t+=dt
            if self.mp_t>0.05: self.mp_t=0;self.mp.send(gs.player)

    def _uspace(self,dt):
        gs=self.gs;kx=self.joy_move.kx;ky=self.joy_move.ky
        keys=pygame.key.get_pressed();spd=300
        if keys[pygame.K_LEFT]  or keys[pygame.K_a] or kx<-0.3: gs.sp_cam_x-=spd*dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d] or kx>0.3:  gs.sp_cam_x+=spd*dt
        if keys[pygame.K_UP]    or keys[pygame.K_w] or ky<-0.3: gs.sp_cam_y-=spd*dt
        if keys[pygame.K_DOWN]  or keys[pygame.K_s] or ky>0.3:  gs.sp_cam_y+=spd*dt
        ax=self.joy_aim.kx;ay=self.joy_aim.ky;am=math.hypot(ax,ay)
        fire=keys[pygame.K_SPACE] or am>0.4
        if fire:
            pbx,pby=gs.pb_pos
            if d2((gs.sp_cam_x,gs.sp_cam_y),(pbx,pby))<400:
                gs.bullets.append(Bullet(gs.sp_cam_x,gs.sp_cam_y,pbx,pby,"player",30))
        for b in gs.bullets: b.update(dt)
        pbx,pby=gs.pb_pos
        for b in gs.bullets:
            if d2((b.x,b.y),(pbx,pby))<30:
                gs.pb_hp=max(0,gs.pb_hp-b.dmg);b.alive=False
                if gs.pb_hp<=0: gs.game_won=True;gs.push("ПОБЕДА!")
        gs.bullets=[b for b in gs.bullets if b.alive]
        for p in gs.particles: p.update(dt)
        gs.particles=[p for p in gs.particles if p.alive]

    def _draw(self):
        s=self.surf
        if self.state=="menu":   self.menu.draw(s,GS.load_info());return
        if self.state=="result": self.res_scr.draw(s,self.gs.game_won);return
        gs=self.gs
        if gs.in_space: self.sp_scr.draw(s,gs);self._djoys(s);return
        night=gs.day_alpha();s.fill(lc(C_BG,C_NIGHT,night))
        gs.world.draw(s,gs.cam_x,gs.cam_y,night)
        for p in gs.particles: p.draw(s,gs.cam_x,gs.cam_y)
        for b in gs.buildings: b.draw(s,gs.cam_x,gs.cam_y,night)
        vsx=int(gs.vega_x-gs.cam_x);vsy=int(gs.vega_y-gs.cam_y)
        nm2=C_NIGHT
        if -300<vsx<SW+300 and -300<vsy<SH+300:
            self._draw_vega(s,vsx,vsy,gs,night)
        for addr,(px2,py2,pc,pnm,pf,phg) in self.mp.peers.items():
            tmp=Character(px2,py2,sc(pc),pnm[:6]);tmp.headgear=phg;tmp.facing=pf
            tmp.draw(s,gs.cam_x,gs.cam_y,night)
        for n in gs.npcs:    n.draw(s,gs.cam_x,gs.cam_y,night)
        for p in gs.pirates: p.draw(s,gs.cam_x,gs.cam_y,night)
        gs.player.draw(s,gs.cam_x,gs.cam_y,night)
        for b in gs.bullets: b.draw(s,gs.cam_x,gs.cam_y)
        if gs.build_type:
            mx,my=pygame.mouse.get_pos();d=BDATA[gs.build_type];sw2,sh2=d["size"]
            tx=(mx+gs.cam_x)//TILE;ty=(my+gs.cam_y)//TILE
            rx=tx*TILE-gs.cam_x;ry=ty*TILE-gs.cam_y
            ov=pygame.Surface((sw2*TILE,sh2*TILE),pygame.SRCALPHA)
            can=gs.can_afford(gs.build_type);ov.fill((0,200,100,65) if can else(200,50,50,65));s.blit(ov,(rx,ry))
            pygame.draw.rect(s,C_GREEN if can else C_DANGER,(rx,ry,sw2*TILE,sh2*TILE),2)
        if night>0.05:
            vl=pygame.Surface((SW,SH),pygame.SRCALPHA);vl.fill((0,5,20,int(night*140)));s.blit(vl,(0,0))
            if night>0.35:
                rng3=random.Random(99)
                for _ in range(int(night*60)): pygame.draw.circle(s,(int(night*160),int(night*160),int(night*160)),(rng3.randint(0,SW),rng3.randint(0,SH//3)),1)
        self._dhud(s,gs);self.tablet.draw(s,gs);self._djoys(s)

    def _djoys(self,s): self.joy_move.draw(s);self.joy_aim.draw(s)

    def _draw_vega(self,s,vsx,vsy,gs,night):
        """Корабль Вега — огромный, больше персонажа в 10-15 раз"""
        nm=C_NIGHT
        # Размеры: ~240×120 пикселей
        W=240; H=120
        vc =lc((20,50,130),nm,night)
        vc2=lc((10,30,90),nm,night)
        vhi=lc((60,120,220),nm,night)
        frc=lc(C_FRAME,nm,night)
        # Тень
        shd=pygame.Surface((W+20,H+10),pygame.SRCALPHA)
        shd.fill((0,0,0,50))
        s.blit(shd,(vsx-W//2+8,vsy-H//4+8))
        # Основной корпус — вытянутый эллипс
        pygame.draw.ellipse(s,vc,(vsx-W//2,vsy-H//4,W,H//2))
        # Нос корабля (острый)
        nose=[( vsx-W//2,     vsy),
              ( vsx-W//2-60,  vsy+10),
              ( vsx-W//2-50,  vsy-10)]
        pygame.draw.polygon(s,vc2,nose)
        pygame.draw.polygon(s,frc,nose,2)
        # Корма (прямоугольная)
        pygame.draw.rect(s,vc2,(vsx+W//2-30,vsy-H//4,30,H//2))
        # Дюзы (3 штуки)
        for dy2 in[-20,0,20]:
            pygame.draw.ellipse(s,sc((180,80,0)),(vsx+W//2,vsy+dy2-8,18,16))
            t2=pygame.time.get_ticks()/300
            gc=int(abs(math.sin(t2))*100)
            pygame.draw.ellipse(s,sc((200+gc,100,0)),(vsx+W//2+2,vsy+dy2-5,10,10))
        # Верхняя надстройка
        pygame.draw.rect(s,vc,(vsx-60,vsy-H//4-30,120,35),border_radius=8)
        pygame.draw.rect(s,frc,(vsx-60,vsy-H//4-30,120,35),2,border_radius=8)
        # Окна
        for i in range(5):
            wx=vsx-80+i*36; wy=vsy-8
            pygame.draw.ellipse(s,lc((180,220,255),nm,night),(wx,wy,22,12))
            pygame.draw.ellipse(s,frc,(wx,wy,22,12),1)
        # Крылья
        lwing=[(vsx-20,vsy+H//4),(vsx+80,vsy+H//4),(vsx+60,vsy+H//4+40),(vsx-40,vsy+H//4+35)]
        rwing=[(vsx-20,vsy-H//4),(vsx+80,vsy-H//4),(vsx+60,vsy-H//4-40),(vsx-40,vsy-H//4-35)]
        pygame.draw.polygon(s,vc2,lwing); pygame.draw.polygon(s,frc,lwing,2)
        pygame.draw.polygon(s,vc2,rwing); pygame.draw.polygon(s,frc,rwing,2)
        # Контур корпуса
        pygame.draw.ellipse(s,frc,(vsx-W//2,vsy-H//4,W,H//2),2)
        # Название
        txt(s,"[ ВЕГА ]",(vsx,vsy-H//4-45),FM,frc,center=True,shadow=True)
        # HP бар
        if gs.vega_hp>0:
            pct=gs.vega_hp/gs.vega_max
            bw=140
            pygame.draw.rect(s,(50,0,0),(vsx-bw//2,vsy+H//4+50,bw,8))
            pygame.draw.rect(s,lc(C_GREEN,nm,night),(vsx-bw//2,vsy+H//4+50,int(bw*pct),8))
            txt(s,f"HP {gs.vega_hp}/{gs.vega_max}",(vsx,vsy+H//4+62),FS,lc(C_TEXT,nm,night),center=True)
        elif gs.vega_hp==0:
            txt(s,"ПОВРЕЖДЁН [E] рядом чтоб починить",(vsx,vsy+H//4+50),FS,C_DANGER,center=True,shadow=True)

    def _dhud(self,s,gs):
        dpanel(s,(4,4,360,24))
        rls=[("Лом",C_WARN,"scrap"),("Руда",C_FRAME,"ore"),("Кри",C_GREEN,"crystal"),("Крд",C_TEXT,"credits")]
        for i,(lb,col,key) in enumerate(rls): txt(s,f"{lb}:{gs.res.get(key,0)}",(10+i*88,6),FS,col)
        dpanel(s,(SW-158,4,154,46))
        sn={1:"Выживание",2:"Колония",3:"Космос"}
        txt(s,f"Этап:{sn.get(gs.stage,'?')}",(SW-154,7),FS,C_FRAME)
        txt(s,f"Нас:{gs.population}",(SW-154,22),FS,C_TEXT)
        txt(s,f"{int(gs.day_time*24):02d}:00",(SW-154,36),FS,C_TEXT2)
        if gs.raid_active: txt(s,f"!! АТАКА!! Пир:{len(gs.pirates)}",(SW//2,42),FM,C_DANGER,center=True,shadow=True)
        if gs.cur_msg:
            w=min(560,FM.size(gs.cur_msg)[0]+20);dpanel(s,(SW//2-w//2,SH//2-58,w,28))
            txt(s,gs.cur_msg,(SW//2,SH//2-54),FM,C_WARN,center=True)
        dpanel(s,(4,SH-34,120,28));hw=int(112*gs.player.hp/gs.player.max_hp)
        pygame.draw.rect(s,(50,0,0),(8,SH-26,112,14));pygame.draw.rect(s,C_GREEN,(8,SH-26,hw,14))
        txt(s,f"HP {gs.player.hp}",(14,SH-24),FS,C_TEXT)
        if gs.player.weapon!="none":
            wd=WEAPONS.get(gs.player.weapon)
            if wd: dpanel(s,(130,SH-34,115,28));txt(s,wd["name"],(134,SH-30),FS,C_FRAME)
        dbtn(s,self.btn_tab,"[ ПЛАНШЕТ ]",hover=self.btn_tab.collidepoint(pygame.mouse.get_pos()),font=FS)
        dbtn(s,self.btn_pick,"СОБРАТЬ",hover=self.btn_pick.collidepoint(pygame.mouse.get_pos()),font=FS)
        dbtn(s,self.btn_run,"БЕЖАТЬ",active=self.run_boost,hover=self.btn_run.collidepoint(pygame.mouse.get_pos()),font=FS)
        if gs.vega_hp>0:
            pct=gs.vega_hp/gs.vega_max
            pygame.draw.rect(s,(40,0,0),(SW//2-60,33,120,8));pygame.draw.rect(s,C_GREEN,(SW//2-60,33,int(120*pct),8))
            txt(s,f"Вега {gs.vega_hp}/{gs.vega_max}",(SW//2,43),FS,C_TEXT2,center=True)
        mw=100;mh=78;mx2=SW-mw-4;my2=SH-mh-4;dpanel(s,(mx2-2,my2-2,mw+4,mh+4))
        scx=mw/(gs.world.w*TILE);scy=mh/(gs.world.h*TILE)
        for(tx,ty),ob in gs.world.objs.items():
            pygame.draw.rect(s,C_WARN if ob=="scrap" else C_FRAME,(mx2+int(tx*TILE*scx),my2+int(ty*TILE*scy),2,2))
        for b in gs.buildings: pygame.draw.rect(s,b.col,(mx2+int(b.tx*TILE*scx),my2+int(b.ty*TILE*scy),4,4))
        for p in gs.pirates: pygame.draw.rect(s,C_DANGER,(mx2+int(p.x*scx),my2+int(p.y*scy),2,2))
        ppx=mx2+int(gs.player.x*scx);ppy=my2+int(gs.player.y*scy)
        pygame.draw.circle(s,C_GREEN,(ppx,ppy),3)
        if self.mp.connected: txt(s,f"MP:{len(self.mp.peers)+1}",(4,SH-52),FS,C_GREEN)
        txt(s,f"FPS:{int(self.clock.get_fps())}",(SW-52,SH-16),FS,C_DIM)

if __name__=="__main__":
    Game().run()