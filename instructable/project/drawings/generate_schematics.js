// Terminal-level wiring diagrams. Repeated net names mean electrical connection.
const fs=require('fs'),path=require('path');
const sharp=require('/Users/scalarmac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const E=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;');
const T=(x,y,s,z=22,c='#263744',a='start')=>`<text x="${x}" y="${y}" font-size="${z}" fill="${c}" text-anchor="${a}">${E(s)}</text>`;
const R=(x,y,w,h,fill='#f4f7f9')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="5" fill="${fill}" stroke="#526b7a" stroke-width="2"/>`;
const W=(points,c='#296b8d',extra='')=>`<polyline points="${points}" fill="none" stroke="${c}" ${extra.includes('stroke-width')?'':'stroke-width="3"'} ${extra}/>`;
const P=(x,y)=>`<circle cx="${x}" cy="${y}" r="5" fill="white" stroke="#263744" stroke-width="2"/>`;
const D=(x,y,c='#296b8d')=>`<circle cx="${x}" cy="${y}" r="6" fill="${c}"/>`;
const G=(x,y)=>W(`${x},${y} ${x},${y+18}`,'#303840')+W(`${x-18},${y+18} ${x+18},${y+18}`,'#303840')+W(`${x-11},${y+25} ${x+11},${y+25}`,'#303840')+W(`${x-4},${y+32} ${x+4},${y+32}`,'#303840');
const N=(x,y,name,c='#263744',dir=1)=>W(`${x},${y} ${x+dir*70},${y}`,c)+T(x+dir*80,y+7,name,19,c,dir===1?'start':'end');
const B=(title,sub,w=1900,h=1400)=>`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><style>text{font-family:Arial,sans-serif}</style><rect width="${w}" height="${h}" fill="white"/>${T(55,55,title,33)}${T(55,95,sub,20)}${T(55,h-26,'REVIEW • dimensions/positions schematic • same net name = same wire network • dots = junctions • © 2026 crackpotgumption / CC BY 4.0',16,'#687985')}`;

let a=B('06 — Mega, I²C bus and Start switch','Individual pin connections. The Mega receives power and serial through USB from the host.');
a+=R(80,140,430,70)+T(100,185,'Host computer USB power + serial',23);
a+=W('280,210 280,260','#526b7a')+R(100,260,400,1000)+T(125,305,'ARDUINO MEGA 2560',26)+T(125,340,'USB connector',18);
a+=R(1110,250,570,330)+T(1130,290,'ADAFRUIT #6318 — I²C / logic',25)+T(1130,325,'Address 0x20',20);
a+=R(1110,680,570,330)+T(1130,720,'TCA9548A — upstream I²C',25)+T(1130,755,'Address 0x70; channels on sheet 07',20);
// Shared SDA and SCL, with a white crossing gap where SDA branch crosses SCL.
a+=W('500,400 1110,400','#286e99')+W('500,460 1110,460','#397a45');
a+=W('800,400 800,830 1110,830','#286e99');
a+=W('792,460 808,460','white','stroke-width="10"')+W('800,445 800,475','#286e99');
a+=W('860,460 860,890 1110,890','#397a45')+D(800,400)+D(860,460,'#397a45');
for(const [name,y] of [['D20 / SDA',400],['D21 / SCL',460]])a+=T(480,y-12,name,21,'#263744','end')+P(500,y);
for(const y of [400,830])a+=P(1110,y)+T(1130,y+7,'SDA',21);
for(const y of [460,890])a+=P(1110,y)+T(1130,y+7,'SCL',21);
a+=T(650,380,'SDA',19,'#286e99')+T(650,492,'SCL',19,'#397a45');
a+=T(125,560,'5 V pin: no external rail connection',18);
a+=T(480,627,'GND',22,'#263744','end')+P(500,620)+N(500,620,'DC_GND','#303840');
// Net labels placed inside the right margin, each ending on the actual pin.
a+=P(1680,380)+W('1680,380 1760,380','#be4b35')+T(1750,355,'Vcc',20)+T(1760,415,'DEDICATED_5V',18,'#be4b35','end');
a+=P(1680,510)+W('1680,510 1760,510','#303840')+G(1760,510)+T(1655,517,'GND',20,'#263744','end')+T(1760,565,'DC_GND',18,'#303840','end');
a+=P(1680,810)+W('1680,810 1790,810','#be4b35')+T(1655,817,'VCC / VIN',20,'#263744','end')+T(1810,790,'DEDICATED_5V',17,'#be4b35','end');
a+=P(1680,940)+W('1680,940 1760,940','#303840')+G(1760,940)+T(1655,947,'GND',20,'#263744','end')+T(1760,995,'DC_GND',18,'#303840','end');
// Start button: open contact, return to ground. Pullup is in firmware.
a+=T(480,713,'D24',22,'#263744','end')+P(500,705)+W('500,705 625,705','#6c4b87')+P(625,705)+P(720,705)+W('625,705 702,675','#303840')+W('720,705 740,705 740,765','#303840')+G(740,765);
a+=T(600,660,'START — normally open',20)+T(125,750,'pinMode(D24, INPUT_PULLUP)',18)+T(600,825,'DC_GND',18,'#303840');
const pins=[14,15,16,17,18];pins.forEach((pin,i)=>{let y=900+i*65;a+=T(480,y+7,`D${pin}`,22,'#263744','end')+P(500,y)+N(500,y,`LED${i}_DATA`,'#6c4b87');});
a+=T(900,1120,'LED0_DATA … LED4_DATA continue to the collar DIN pins on sheet 07.',22);
a+=T(900,1160,'Driver coil power and switched outputs are drawn on sheet 08.',22);
a+=T(900,1210,'Driver Vcc and mux VCC / VIN use the dedicated 5 V supply, not the Mega 5 V pin.',20);
a+=T(900,1245,'DEDICATED_5V is the same supply rail drawn on sheet 07.',20);
a+='</svg>';

let b=B('07 — Five sensors and five illuminated collars','Each drawn collar and sensor is a separate physical device. Repeat net names connect to sheets 06 and 08.',2200,1500);
b+=R(70,145,420,115)+T(90,180,'5 V / 10 A collar power supply',24)+T(90,220,'+ → master +5 V; 0 V → DC_GND',20);
b+=W('490,180 1850,180 1850,1340','#be4b35')+T(950,164,'DEDICATED_5V — MASTER BLOCK → 18 AWG FEEDER → DECK BUS',20,'#a33f2d');
b+=W('490,230 2050,230 2050,1340','#303840')+T(950,256,'COMMON DC GROUND → DECK GROUND BUS',20,'#303840');
b+=R(70,320,380,1040)+T(90,360,'TCA9548A',27)+T(90,395,'Downstream channels',21)+T(90,430,'Channels 5–7 unused',19);
for(let i=0;i<5;i++){
 let y=500+i*170;
 b+=T(425,y-20,`Channel ${i}`,20,'#263744','end')+T(425,y+17,`SD${i}`,20,'#263744','end')+T(425,y+67,`SC${i}`,20,'#263744','end');
 b+=P(450,y+10)+P(450,y+60)+W(`450,${y+10} 610,${y+10}`,'#286e99')+W(`450,${y+60} 610,${y+60}`,'#397a45');
 b+=R(610,y-30,410,125)+T(630,y-2,`MPU6050 — target ${i}`,23)+P(610,y+10)+P(610,y+60)+T(630,y+25,'SDA',19)+T(630,y+73,'SCL',19);
 b+=T(995,y+25,'VCC',18,'#263744','end')+P(1020,y+18)+W(`1020,${y+18} 1110,${y+18}`,'#be4b35')+T(1110,y-2,'DEDICATED_5V',16,'#be4b35','end');
 b+=T(995,y+73,'GND',18,'#263744','end')+P(1020,y+65)+W(`1020,${y+65} 1110,${y+65}`,'#303840')+G(1110,y+65);
 b+=T(740,y+118,'0x68; AD0 low; Y vertical',18);
 // Independent data net into DIN; output not chained to another collar.
 b+=R(1430,y-30,330,125,'#eef5ef')+T(1450,y-2,`COLLAR ${i} — 19 pixels`,22);
 b+=N(1430,y+30,`LED${i}_DATA`,'#6c4b87',-1)+P(1430,y+30)+T(1450,y+37,'DIN',19);
 b+=T(1730,y+25,'+5 V',18,'#263744','end')+P(1760,y+18)+W(`1760,${y+18} 1850,${y+18}`,'#be4b35')+D(1850,y+18,'#be4b35');
 b+=T(1730,y+73,'GND',18,'#263744','end')+P(1760,y+65)+W(`1760,${y+65} 2050,${y+65}`,'#303840')+D(2050,y+65,'#303840');
 // White bridge on the ground lead across the +5 V trunk; no junction dot there.
 b+=W(`1840,${y+65} 1860,${y+65}`,'white','stroke-width="10"')+W(`1850,${y+55} 1850,${y+75}`,'#be4b35');
}
b+=T(70,1410,'All five MPU6050 breakout VCC pins use DEDICATED_5V. All ground symbols join DC_GND.',20);
b+='</svg>';

let c=B('08 — Five 12 V valve coils and driver terminals','Wire each coil between its driver + terminal and matching numbered switched output. No coil connects to a Mega pin.');
c+=R(60,185,395,190,'#fbeeea')+T(80,225,'12 V / 5 A supply',26)+T(80,270,'+12 V',22)+T(80,330,'0 V return',22);
c+=R(680,180,520,1050)+T(700,225,'ADAFRUIT #6318',27)+T(700,260,'Coil-power terminals',22);
c+=W('455,280 680,280 780,280 780,1060','#be4b35')+P(680,280)+T(700,310,'V+ / +12 V input',19);
c+=W('455,340 560,340 560,1160 680,1160','#303840')+P(680,1160)+T(700,1167,'GND',21)+G(560,1160)+T(400,1240,'DC_GND',20);
c+=T(60,470,'Use the master 12 V and ground',21)+T(60,503,'distribution blocks on these runs.',21);
for(let i=0;i<5;i++){
 let y=380+i*150;
 c+=W(`780,${y} 1200,${y}`,'#be4b35')+D(780,y,'#be4b35')+P(1200,y)+T(1170,y-12,`+ / V+`,20,'#263744','end');
 c+=W(`1200,${y} 1320,${y} 1320,${y+40} 1400,${y+40}`,'#be4b35');
 c+=P(1200,y+80)+T(1170,y+87,`${i} / A${i}`,21,'#263744','end')+W(`1200,${y+80} 1600,${y+80} 1600,${y+40} 1510,${y+40}`,'#286e99');
 c+=P(1400,y+40)+P(1510,y+40)+`<path d="M1400 ${y+40} q 11 -38 22 0 q 11 -38 22 0 q 11 -38 22 0 q 11 -38 22 0 q 11 -38 22 0" fill="none" stroke="#303840" stroke-width="3"/>`;
 c+=T(1455,y-12,`VALVE ${i} — 12 V COIL`,21,'#263744','middle');
}
c+=T(700,1110,'Numbered outputs are switched coil returns.',20);
c+=T(60,600,'Driver logic Vcc and SDA/SCL:',21)+T(60,633,'see sheet 06.',21);
c+=T(60,710,'+ terminals share the board V+ supply.',20)+T(60,743,'Built-in output drivers / flyback protection.',19);
c+=T(60,835,'Do not confuse rear A0–A4 output labels',19)+T(60,868,'with the separate I²C address jumpers.',19);
c+=T(700,1280,'OFF / de-energized: valve routes air to the top of its cylinder.',23);
c+='</svg>';
(async()=>{for(const [n,svg] of [['06_controller_schematic',a],['07_sensor_collar_wiring',b],['08_valve_coil_wiring',c]]){fs.writeFileSync(path.join(__dirname,n+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(__dirname,n+'.png'));}console.log('Created three terminal-level schematic sheets.');})();
