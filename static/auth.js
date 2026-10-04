const apiRequest = async (url, data) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.detail || 'Request failed.');
  return result;
};

document.querySelectorAll('.password-toggle').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordTarget);
    input.type = input.type === 'password' ? 'text' : 'password';
    button.textContent = input.type === 'password' ? 'Show' : 'Hide';
  });
});

document.getElementById('loginForm')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  try {
    await apiRequest('/api/login', { username, password });
    window.location.assign('/dashboard');
  } catch (error) {
    alert(error.message);
  }
});

document.getElementById('signupForm')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = document.getElementById('signupUsername').value.trim();
  const password = document.getElementById('signupPassword').value;
  const confirmPassword = document.getElementById('signupPasswordConfirm').value;
  if (password !== confirmPassword) {
    alert('Passwords do not match.');
    return;
  }
  try {
    await apiRequest('/api/signup', {
      username,
      password,
      role: document.querySelector('input[name="signupRole"]:checked').value,
    });
    window.location.assign('/dashboard');
  } catch (error) {
    alert(error.message);
  }
});
