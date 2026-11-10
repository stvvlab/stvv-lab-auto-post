from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
W,H=1600,900
im=Image.new("RGB",(W,H),"#06182d");d=ImageDraw.Draw(im)
Y="#ffda14";N="#06182d";white="#f4f7fb"
d.polygon([(0,0),(220,0),(0,280)],fill=Y)
d.rectangle((0,0,W,13),fill=Y)
d.rectangle((60,70,1540,145),fill="#153452")
d.rectangle((60,205,1540,420),outline=Y,width=6)
d.rectangle((60,485,1540,740),fill="#112e4b")
d.line((800,505,800,715),fill=Y,width=4)
f="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
def t(x,y,s,z,c):d.text((x,y),s,font=ImageFont.truetype(f,z),fill=c)
t(90,82,"STVV LAB  /  SAMURAI BLUE",45,white)
t(105,235,"小久保玲央ブライアン",81,white)
t(105,341,"日本代表メンバー選出",47,Y)
t(115,522,"11.14 SAT",47,Y);t(115,598,"日本 vs ブラジル",47,white);t(115,674,"19:15 JST",28,white)
t(865,522,"11.17 TUE",47,Y);t(865,598,"日本 vs パラグアイ",45,white);t(865,674,"22:10 JST",28,white)
t(85,802,"GK  |  SINT-TRUIDENSE V.V.  |  2026 NOVEMBER",29,white)
Path("generated").mkdir(exist_ok=True)
im.save("generated/2026-11-12_kokubo_japan_callup.png",optimize=True)
