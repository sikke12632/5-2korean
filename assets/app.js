(function(){
  var KEY='gugeo52-v1';
  function load(){try{return JSON.parse(localStorage.getItem(KEY))||{}}catch(e){return{}}}
  function save(d){try{localStorage.setItem(KEY,JSON.stringify(d))}catch(e){}}
  window.P={
    get:load,
    isDone:function(s){return !!(load().done||{})[s]},
    markDone:function(s){var d=load();d.done=d.done||{};d.done[s]=1;d.last=s;save(d)},
    touch:function(s){var d=load();d.last=s;save(d)},
    last:function(){return load().last||null},
    doneCount:function(){return Object.keys(load().done||{}).length},
    wrong:function(qid){var d=load();d.wrong=d.wrong||{};d.wrong[qid]=1;save(d)},
    isWrong:function(qid){return !!(load().wrong||{})[qid]},
    reset:function(){try{localStorage.removeItem(KEY)}catch(e){}}
  };
  // 카드 펼치기
  document.addEventListener('click',function(e){
    var c=e.target.closest('.card'); if(c) c.classList.toggle('open');
  });
  // 퀴즈
  window.initQuiz=function(slug,total){
    var solved=0;
    document.querySelectorAll('.quiz').forEach(function(q){
      var fb=q.querySelector('.fb'), qid=q.dataset.qid;
      q.querySelectorAll('.opt').forEach(function(o){
        o.addEventListener('click',function(){
          if(q.dataset.done)return;
          if(o.dataset.a==='1'){
            o.classList.add('ok'); fb.textContent='정답입니다!'; fb.className='fb ok'; q.dataset.done='1';
            q.querySelectorAll('.opt').forEach(function(x){if(x!==o)x.disabled=true});
            solved++;
            if(total&&solved===total){
              if(slug)P.markDone(slug);
              var b=document.getElementById('doneBanner'); if(b){b.classList.add('show');b.scrollIntoView({behavior:'smooth',block:'center'});}
            }
          }else{
            o.classList.add('no'); o.disabled=true;
            fb.textContent='다시 한번 생각해 보세요.'; fb.className='fb no';
            if(qid)P.wrong(qid);
            setTimeout(function(){o.classList.remove('no')},800);
          }
        });
      });
    });
  };
})();
