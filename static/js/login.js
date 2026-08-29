const emailEl   = document.getElementById('email');
const passEl    = document.getElementById('password');
const loginBtn  = document.getElementById('login-btn');
const errorMsg  = document.getElementById('error-msg');
const togglePw  = document.getElementById('toggle-pw');
const eyeIcon   = document.getElementById('eye-icon');
const formSec   = document.getElementById('form-section');
const successSec = document.getElementById('success-screen');

togglePw.addEventListener('click', () => {
  const show = passEl.type === 'password';
  passEl.type = show ? 'text' : 'password';
  eyeIcon.innerHTML = show
    ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>`
    : `<path d="M1 12S5 5 12 5s11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>`;
});

[emailEl, passEl].forEach(el =>
  el.addEventListener('input', () => errorMsg.classList.remove('show'))
);

loginBtn.addEventListener('click', () => {
  const email = emailEl.value.trim();
  const pass  = passEl.value;

  if (!email || !pass) {
    errorMsg.textContent = 'Please enter both your email and password.';
    errorMsg.classList.add('show');
    return;
  }

  loginBtn.classList.add('loading');
  loginBtn.disabled = true;
  errorMsg.classList.remove('show');

  fetch('/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email: email, password: pass })
  })
  .then(response => {
    return response.json().then(data => ({
      status: response.status,
      data: data
    }));
  })
  .then(({ status, data }) => {
    loginBtn.classList.remove('loading');
    if (status === 200 && data.success) {
      formSec.style.display = 'none';
      successSec.classList.add('show');
      
      const titleEl = successSec.querySelector('.success-title');
      const subEl   = successSec.querySelector('.success-sub');
      
      // Phase 1: Authenticating
      if (titleEl) titleEl.textContent = 'Authenticating...';
      if (subEl) subEl.textContent = 'Verifying security credentials...';
      
      setTimeout(() => {
        // Phase 2: Loading Dashboard
        if (titleEl) titleEl.textContent = 'Loading Dashboard...';
        if (subEl) subEl.textContent = 'Initializing stability management parameters...';
        
        setTimeout(() => {
          // Phase 3: Redirect
          window.location.href = data.redirect;
        }, 1000);
      }, 1000);
    } else {
      loginBtn.disabled = false;
      errorMsg.textContent = data.message || 'Credentials not recognised. Please try again.';
      errorMsg.classList.add('show');
      passEl.value = '';
      passEl.focus();
    }
  })
  .catch(err => {
    loginBtn.classList.remove('loading');
    loginBtn.disabled = false;
    errorMsg.textContent = 'Server connection failed. Please ensure MareTide services are running.';
    errorMsg.classList.add('show');
  });
});

document.addEventListener('keydown', e => { if (e.key === 'Enter') loginBtn.click(); });