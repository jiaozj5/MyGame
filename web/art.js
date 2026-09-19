// Original code-drawn pixel scenery; no image downloads or external assets.
const palettes = {
  spring: {sky:'#d9e8dc',cloud:'#f1f1d9',far:'#b8ccad',hill:'#a3bf91',grass:'#bdcb90',dark:'#67865a',leaf:'#829f69',light:'#9eb87b',river:'#a8c8be',water:'#c9ded0',roof:'#a98466',wall:'#e1d4ad'},
  autumn: {sky:'#e6e3cc',cloud:'#f5edcf',far:'#c7c7a0',hill:'#b5b988',grass:'#c8bd85',dark:'#818552',leaf:'#ae9f5e',light:'#c5b373',river:'#b3c6b1',water:'#d3dac0',roof:'#ac8266',wall:'#e5d5ad'},
  evening: {sky:'#c9cfc3',cloud:'#e6d9bb',far:'#a4b2a1',hill:'#899e84',grass:'#a7b58a',dark:'#536d59',leaf:'#73866a',light:'#8f9e79',river:'#8daea6',water:'#b8c7b6',roof:'#967563',wall:'#d8c5a0'}
};

export function drawScene(canvas, options={}) {
  if (!canvas) return;
  canvas.width=480; canvas.height=260;
  const c=canvas.getContext('2d'); c.imageSmoothingEnabled=false; c.scale(2,2);
  const scene=options.scene||'town', old=options.age>=60, dusk=scene==='evening'||options.finished;
  const p=palettes[dusk?'evening':old?'autumn':'spring'];
  const r=(x,y,w,h,color)=>{c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));};
  let seed=1741;
  const rand=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};
  r(0,0,240,130,p.sky);
  // The sun and stepped clouds.
  r(176,14,13,13,'#eadfb1');r(173,17,19,7,'#eadfb1');
  const cloud=(x,y,w)=>{r(x+5,y,w-10,2,p.cloud);r(x+2,y+2,w-4,3,p.cloud);r(x,y+5,w,2,p.cloud);};
  cloud(24,18,31);cloud(112,12,22);cloud(202,29,25);cloud(74,35,18);
  for(let x=0;x<240;x+=3){const h=Math.round(43+Math.sin(x*.025)*7+Math.sin(x*.08)*4);r(x,h,3,40,p.far);}
  for(let x=0;x<240;x+=3){const h=Math.round(56+Math.sin(x*.034+1)*7+Math.sin(x*.075)*4);r(x,h,3,38,p.hill);}
  r(0,80,240,50,p.grass);
  // Distant hedges and terraced fields.
  for(let x=0;x<240;x+=8){r(x,74+Math.round(Math.sin(x)*2),9,5,'#95ae7b');r(x+2,73+Math.round(Math.sin(x)*2),5,3,'#a8ba83');}
  r(6,83,57,17,'#b4bd81');for(let i=0;i<5;i++)r(6,85+i*3,57,1,'#98a875');
  r(70,89,156,3,'#d4cba4');r(64,91,166,4,'#dbd1ad');
  function roof(x,y,w,color){for(let n=0;n<7;n++)r(x+7-n,y+n,w-14+n*2,1,color);r(x-1,y+7,w+2,2,'#88745d');for(let q=0;q<w-8;q+=5)r(x+4+q,y+5,3,1,'#be9a78');}
  function house(x,y,w,h,color=p.wall){
    r(x+2,y+8,w-4,h,color);r(x+2,y+8,3,h,'#c5bc94');r(x+3,y+8,w-6,2,'#bcaa83');
    roof(x,y,w,p.roof);r(x+w/2-3,y+h-1,6,9,'#84775e');r(x+w/2-2,y+h,2,8,'#a3926c');
    for(let wx=x+7;wx<x+w-5;wx+=13){if(Math.abs(wx-(x+w/2-3))<6)continue;r(wx,y+13,6,7,'#7e8d79');r(wx+1,y+14,4,4,dusk?'#dec58c':'#becbb0');r(wx+3,y+14,1,5,'#899776');}
    r(x+3,y+h+7,w-6,2,'#bbb58c');
  }
  house(74,63,28,18);house(105,55,34,26);house(140,65,27,17);
  r(115,50,4,8,'#b7b49a');r(114,49,6,2,'#a29f85');
  if(scene==='school'){
    house(166,59,49,29,'#e8debb');r(185,52,2,37,'#998e75');r(187,52,10,6,'#bc8465');r(185,68,12,5,'#8b9c7a');r(190,69,3,3,'#d9ddb9');
  } else if(scene==='hospital'){
    house(164,61,49,27,'#e8e5cb');r(184,70,10,10,'#efebd4');r(188,71,2,8,'#879d74');r(185,74,8,2,'#879d74');
  } else if(scene==='work'){
    house(163,63,50,25,'#d1ccb1');r(166,57,5,12,'#a9ae98');r(207,52,5,16,'#a1a58f');for(let n=0;n<4;n++)r(171+n*10,76,6,9,'#90a291');
  } else {
    house(169,60,43,28);r(169,59,43,1,'#d8ccaa');
    r(208,74,14,3,'#f0e2b8');r(208,77,14,7,'#c8ba8c');r(213,79,4,5,'#b99976');
  }
  // Village square, stone walkway, low fence.
  r(137,92,70,7,'#d4c5a2');r(151,99,37,5,'#d4c5a2');r(166,104,27,7,'#d4c5a2');
  for(let i=0;i<15;i++){let x=138+rand()*67,y=92+rand()*7;r(x,y,3,1,'#b7ad8c');}
  for(let x=81;x<130;x+=7){r(x,87,2,8,'#aa9f79');}r(79,89,53,1,'#b7aa80');r(80,92,51,1,'#b7aa80');
  function tree(x,y,size=1){
    r(x+8*size,y+11*size,3*size,15*size,'#8f8863');r(x+3*size,y+18*size,17*size,3*size,'#a5b681');
    r(x+4*size,y+3*size,12*size,16*size,p.dark);r(x,y+7*size,21*size,10*size,p.dark);
    r(x+5*size,y,10*size,17*size,p.leaf);r(x+1*size,y+5*size,16*size,9*size,p.leaf);
    r(x+5*size,y+2*size,7*size,5*size,p.light);r(x+2*size,y+8*size,5*size,4*size,p.light);r(x+11*size,y+10*size,7*size,5*size,p.leaf);
    r(x+2*size,y+13*size,3*size,2*size,p.dark);r(x+10*size,y+16*size,5*size,2*size,p.dark);
  }
  tree(53,59,.8);tree(215,62,1);tree(19,67,1.2);tree(1,58,1);tree(150,73,.55);
  // Reeds and creek with a deliberately stepped bank.
  for(let x=0;x<240;x+=3){let yy=Math.round(109+7*Math.sin(x*.023));r(x,yy-2,3,23,'#9ab395');r(x,yy,3,25,p.river);}
  for(let n=0;n<70;n++){let x=rand()*240,y=116+rand()*14;if(y>110+7*Math.sin(x*.023))r(x,y,3+rand()*7,1,n%3===0?p.water:'#96bab0');}
  // A small timber bridge on the east bank.
  r(179,104,9,26,'#b7a17d');r(178,107,11,2,'#c8b18c');for(let y=105;y<130;y+=4)r(179,y,9,1,'#938c6e');r(177,102,2,27,'#93896b');r(188,102,2,27,'#93896b');r(176,110,3,2,'#b2a078');r(188,119,3,2,'#b2a078');
  for(let n=0;n<65;n++){let x=rand()*240,y=96+rand()*13;if(x>135&&x<207)continue;r(x,y,1,2,'#9eae77');if(n%6===0)r(x,y-1,2,1,old?'#dfc087':'#ead9ad');}
  // A washing line, bicycle, and two tiny people give the town a lived-in scale.
  r(103,89,1,10,'#9c9270');r(126,89,1,10,'#9c9270');r(103,90,24,1,'#a69c77');r(108,91,4,5,'#e6dfbc');r(116,91,5,4,'#91a58b');
  r(204,93,3,3,'#7d8b71');r(212,93,3,3,'#7d8b71');r(205,93,8,1,'#b08e6a');r(209,89,1,5,'#a68e6c');r(210,89,3,1,'#7d8b71');
  function person(x,y,shirt,small=false){r(x+1,y,3,2,old?'#d1d0b7':'#615f50');r(x+1,y+2,3,3,'#d8b992');r(x,y+5,5,small?4:6,shirt);r(x+1,y+(small?9:11),1,3,'#66735f');r(x+3,y+(small?9:11),1,3,'#66735f');}
  person(scene==='river'?165:145,91,'#be9572',options.age<15);person(159,89,'#7f957b');
  // Foreground leaves and little swallows.
  tree(-8,94,1.35);tree(223,101,1.1);
  r(157,24,2,1,'#8ba38c');r(160,25,1,1,'#8ba38c');r(161,24,2,1,'#8ba38c');r(146,31,2,1,'#8ba38c');r(149,32,1,1,'#8ba38c');r(150,31,2,1,'#8ba38c');
  if(scene==='home'){r(94,80,3,3,'#e1c995');r(133,73,3,3,'#e1c995');}
  if(dusk){r(83,76,4,4,'#e3cb91');r(118,69,4,4,'#e3cb91');r(182,74,4,4,'#e3cb91');}
}

export function drawPortrait(canvas, person={}){
  if(!canvas)return;canvas.width=24;canvas.height=28;const c=canvas.getContext('2d');c.imageSmoothingEnabled=false;
  const r=(x,y,w,h,color)=>{c.fillStyle=color;c.fillRect(x,y,w,h);};
  const age=person.age??24,role=person.id||'player',old=age>=60;
  const variation=[...role].reduce((sum,char)=>(sum*31+char.charCodeAt(0))>>>0,0);
  const female=role==='mother'||role==='partner'||(!['father','friend','player'].includes(role)&&variation%2===0);
  const skin=['#dbb993','#c49d7b','#af8566','#e3c7a4'][variation%4];
  r(0,0,24,28,person.alive===false?'#deded3':'#e0e6cf');r(3,24,18,4,'#ccd5ba');
  r(7,5,10,13,old?'#b5b5a2':'#676555');r(6,7,12,female?14:7,old?'#b5b5a2':'#676555');
  r(8,8,8,11,skin);r(7,10,10,5,skin);r(8,8,3,2,'#bf9e7e');
  r(9,12,1,1,'#655f4e');r(14,12,1,1,'#655f4e');r(11,16,3,1,'#b88b6a');
  r(8,5,8,3,old?'#c5c4b0':'#605f50');r(7,8,2,3,old?'#c5c4b0':'#605f50');
  const shirt=['#8b9d7a','#b49679','#829389','#9291a0','#b68e75','#789a96','#b19d67'][variation%7];
  r(7,20,10,8,shirt);r(5,22,14,6,shirt);r(10,19,4,3,'#d5af88');r(10,22,4,1,'#c4c5a0');
  if(person.alive===false){r(19,2,3,6,'#9c9d8d');r(17,4,7,2,'#9c9d8d');}
}
