// Avoid `console` errors in browsers that lack a console.
(function() {
    var method;
    var noop = function () {};
    var methods = [
        'assert', 'clear', 'count', 'debug', 'dir', 'dirxml', 'error',
        'exception', 'group', 'groupCollapsed', 'groupEnd', 'info', 'log',
        'markTimeline', 'profile', 'profileEnd', 'table', 'time', 'timeEnd',
        'timeline', 'timelineEnd', 'timeStamp', 'trace', 'warn'
    ];
    var length = methods.length;
    var console = (window.console = window.console || {});

    while (length--) {
        method = methods[length];

        // Only stub undefined methods.
        if (!console[method]) {
            console[method] = noop;
        }
    }
}());

// Place any jQuery/helper plugins in here.

$(document).ready(function(){
	$(".contentsPanel").each(function() {                
		$(this).prepend('<div class="hidePanel">[hide]</div><div class="showPanel">[show]</div>');
	});
	
	
    $(".hidePanel").click(function(){
		$( this ).siblings('ul').hide( 150, function() { 
			$(this).parent().addClass('minimizedPanel');
		});
    });
    $(".showPanel").click(function(){
		$( this ).siblings('ul').show( 150, function() { 
			$(this).parent().removeClass('minimizedPanel');
		});
    });
	
	
});

// ====== Abas (conteúdo/discussão) ======
function openTab(tabId){
  document.querySelectorAll('.np-article .np-article-body, .np-article .np-discussion')
    .forEach(el => el.style.display = 'none');

  document.querySelectorAll('.np-article-tabs a')
    .forEach(a => a.classList.remove('active'));

  if(tabId === 'conteudo'){
    const body = document.querySelector('.np-article .np-article-body');
    const link = document.querySelector('.np-article-tabs a[data-tab="conteudo"]');
    if(body) body.style.display = '';
    if(link) link.classList.add('active');
  } else {
    const disc = document.querySelector('.np-article .np-discussion');
    const link = document.querySelector('.np-article-tabs a[data-tab="discussao"]');
    if(disc) disc.style.display = '';
    if(link) link.classList.add('active');
  }
}

// Inicializa abas ao carregar
document.addEventListener('DOMContentLoaded', function(){
  const params = new URLSearchParams(location.search);
  const tab = params.get('tab') || 'conteudo';
  openTab(tab);

  // Se já tem cookie de login, mostra no console
  const user = getCookie("netpedia_user");
  if(user){
    console.log("Bem-vindo de volta, " + user);
  }
});

// ====== Funções de Cookie ======
function setCookie(name, value, days){
  let expires = "";
  if(days){
    const d = new Date();
    d.setTime(d.getTime() + (days*24*60*60*1000));
    expires = "; expires=" + d.toUTCString();
  }
  document.cookie = name + "=" + encodeURIComponent(value) + expires + "; path=/";
}

function getCookie(name){
  const cookies = document.cookie.split(";");
  for(let c of cookies){
    c = c.trim();
    if(c.indexOf(name + "=") === 0){
      return decodeURIComponent(c.substring(name.length + 1));
    }
  }
  return null;
}

function eraseCookie(name){
  document.cookie = name + "=; Max-Age=0; path=/";
}

// ====== Exemplo: intercepta formulário de login ======
document.addEventListener("submit", function(e){
  if(e.target.matches(".np-form-login")){
    e.preventDefault();
    const user = e.target.querySelector("input[name=username]").value;
    const pass = e.target.querySelector("input[name=password]").value;

    // aqui você poderia enviar via fetch() para o backend validar
    // mas por enquanto só vamos salvar cookie de usuário
    if(user && pass){
      setCookie("netpedia_user", user, 7); // dura 7 dias
      alert("Logado como " + user);
      location.href = "/"; // redireciona pra home
    }
  }

  if(e.target.matches(".np-form-register")){
    e.preventDefault();
    const user = e.target.querySelector("input[name=username]").value;
    const pass = e.target.querySelector("input[name=password]").value;

    if(user && pass){
      setCookie("netpedia_user", user, 7);
      alert("Conta criada e logado como " + user);
      location.href = "/";
    }
  }
});

// ====== Menu Hambúrguer ======
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menu-toggle");
  const panel = document.getElementById("mw-panel");
  const closeBtn = document.getElementById("menu-close");

  let startX = 0;
  let currentX = 0;

  if(toggle && panel){
    toggle.addEventListener("click", () => {
      panel.classList.add("open");
    });
  }

  if(closeBtn && panel){
    closeBtn.addEventListener("click", () => {
      panel.classList.remove("open");
    });
  }

  // ===== Swipe para fechar =====
  panel.addEventListener("touchstart", (e) => {
    startX = e.touches[0].clientX;
  });

  panel.addEventListener("touchmove", (e) => {
    currentX = e.touches[0].clientX;
  });

  panel.addEventListener("touchend", () => {
    // Se arrastou mais de 80px pra esquerda -> fecha
    if(startX - currentX > 80){
      panel.classList.remove("open");
    }
    startX = 0;
    currentX = 0;
  });
});

// ==============================
// Vector 1 - Links
// ==============================

// Ao carregar, detecta links internos e marca se existem ou não
document.addEventListener("DOMContentLoaded", function() {
  const links = document.querySelectorAll("#content a");

  links.forEach(link => {
    // Verifica se link interno para página do Netpédia
    if(link.getAttribute("href")?.startsWith("/article/")) {
      fetch(link.href, { method: "HEAD" }) // HEAD request apenas
        .then(response => {
          if(response.ok) {
            link.classList.add("exists"); // página existe
          } else {
            link.classList.add("not-exists"); // página não existe
          }
        })
        .catch(() => {
          link.classList.add("not-exists");
        });
    }
  });
});
