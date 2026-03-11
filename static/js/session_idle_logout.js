(function () {
  const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
  const WARNING_5_MIN_MS = 5 * 60 * 1000;
  const WARNING_1_MIN_MS = 60 * 1000;

  const badge = document.getElementById('idle-timer-badge');
  const logoutForm = document.getElementById('idle-logout-form');
  if (!badge || !logoutForm) return;

  let lastActivityAt = Date.now();
  let warnedAt5 = false;
  let warnedAt1 = false;

  function formatMMSS(ms) {
    const totalSec = Math.max(0, Math.ceil(ms / 1000));
    const mm = String(Math.floor(totalSec / 60)).padStart(2, '0');
    const ss = String(totalSec % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  }

  function resetIdleTimer() {
    lastActivityAt = Date.now();
    warnedAt5 = false;
    warnedAt1 = false;
  }

  function logoutNow() {
    try {
      logoutForm.submit();
    } catch (_e) {
      window.location.href = '/accounts/login/';
    }
  }

  function tick() {
    const elapsed = Date.now() - lastActivityAt;
    const remaining = IDLE_TIMEOUT_MS - elapsed;

    badge.textContent = `Session: ${formatMMSS(remaining)}`;

    if (!warnedAt5 && remaining <= WARNING_5_MIN_MS && remaining > WARNING_1_MIN_MS) {
      warnedAt5 = true;
      window.alert('You will be logged out in 5 minutes due to inactivity.');
    }

    if (!warnedAt1 && remaining <= WARNING_1_MIN_MS && remaining > 0) {
      warnedAt1 = true;
      const keepLoggedIn = window.confirm(
        'You will be logged out in 1 minute due to inactivity.\n\nClick OK to stay logged in, or Cancel to log out now.'
      );
      if (keepLoggedIn) {
        resetIdleTimer();
        return;
      }
      logoutNow();
      return;
    }

    if (remaining <= 0) {
      logoutNow();
    }
  }

  // Reset only on movement (not on focus/tab change, click, key, or scroll).
  const activityEvents = ['mousemove', 'touchmove'];
  activityEvents.forEach((evt) => {
    window.addEventListener(evt, resetIdleTimer, { passive: true });
  });

  setInterval(tick, 1000);
  tick();
})();
