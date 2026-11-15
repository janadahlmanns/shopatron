"""Shopatron message box rendered inside the REWE page (bottom right), with optional buttons.

- The box is a single <div> with a Shadow DOM, which isolates its styles from the shop
  page in both directions.
- A button click stores the button's value on the box element.
- poll() runs a short script in the page (~3x per second) that redraws the box if it is
  missing (e.g. after navigation) and returns a pending answer. This happens locally in
  the browser and issues no requests to the shop.
"""

import uuid

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

POLL_MS = 300

CSS = """
.box { position: fixed; right: 20px; bottom: 20px; z-index: 2147483647; width: 340px;
       background: #fff; color: #222; border: 3px solid #2b7a3d; border-radius: 12px;
       box-shadow: 0 6px 24px rgba(0,0,0,.25); padding: 14px 16px;
       font: 15px/1.4 system-ui, sans-serif; }
.head { display: flex; justify-content: space-between; align-items: center;
        font-weight: 700; color: #2b7a3d; margin-bottom: 6px; }
.msg { white-space: pre-line; max-height: 50vh; overflow-y: auto; }
.buttons { display: flex; gap: 8px; margin-top: 12px; }
.buttons:empty { display: none; }
button { flex: 1; font: inherit; padding: 8px 10px; border-radius: 8px; cursor: pointer;
         border: 1px solid #999; background: #f3f3f3; color: #222; }
button.primary { background: #2b7a3d; border-color: #2b7a3d; color: #fff; font-weight: 600; }
button.close { flex: none; border: none; background: none; padding: 0 4px;
               font-size: 22px; line-height: 1; color: #666; }
button.close:hover { color: #000; }
"""

# Executed in the page: draws the box if missing or outdated, returns and clears a pending
# answer. state = null removes the box.
SYNC_JS = """
({state, css}) => {
  const HOST_ID = 'shopatron-overlay';
  let host = document.getElementById(HOST_ID);
  if (!state) { if (host) host.remove(); return null; }
  if (!host) {
    host = document.createElement('div');
    host.id = HOST_ID;
    host.attachShadow({mode: 'open'});
    document.documentElement.appendChild(host);
  }
  if (host.dataset.key !== state.key) {
    host.dataset.key = state.key;
    host.dataset.answer = '';
    const root = host.shadowRoot;
    root.innerHTML = '<style></style><div class="box"><div class="head"><span>🛒 Shopatron</span></div>'
                   + '<div class="msg"></div><div class="buttons"></div></div>';
    root.querySelector('style').textContent = css;
    if (state.closable) {
      const close = document.createElement('button');
      close.className = 'close';
      close.textContent = '×';
      close.setAttribute('aria-label', 'Schließen');
      close.addEventListener('click', () => {
        root.querySelector('.box').style.display = 'none';
        host.dataset.answer = 'close';
      });
      root.querySelector('.head').appendChild(close);
    }
    root.querySelector('.msg').textContent = state.message;  // rendered as plain text, never as HTML
    const bar = root.querySelector('.buttons');
    for (const b of state.buttons) {
      const btn = document.createElement('button');
      btn.textContent = b.label;
      if (b.primary) btn.className = 'primary';
      btn.addEventListener('click', () => { host.dataset.answer = b.value; });
      bar.appendChild(btn);
    }
  }
  const answer = host.dataset.answer || null;
  host.dataset.answer = '';
  return answer;
}
"""


class Overlay:
    def __init__(self, page: Page):
        self.page = page
        self._state: dict | None = None

    def show(self, message: str, buttons: list[tuple[str, str]] = (), closable: bool = False) -> None:
        """Display a message with optional buttons [(label, value), ...]; the first button is highlighted.

        closable adds a close button (×) to the header; clicking it hides the box and yields "close".
        """
        self._state = {
            "key": uuid.uuid4().hex,  # a new key forces a redraw
            "message": message,
            "closable": closable,
            "buttons": [{"label": label, "value": value, "primary": i == 0}
                        for i, (label, value) in enumerate(buttons)],
        }
        self.poll()

    def poll(self) -> str | None:
        """Ensure the box is present; return the value of a clicked button, if any."""
        try:
            return self.page.evaluate(SYNC_JS, {"state": self._state, "css": CSS})
        except PlaywrightError:
            return None  # page is navigating; retried on the next poll

    def ask(self, message: str, buttons: list[tuple[str, str]]) -> str:
        """Display buttons and block until one is clicked."""
        self.show(message, buttons)
        while (answer := self.poll()) is None:
            self.page.wait_for_timeout(POLL_MS)
        return answer

    def hide(self) -> None:
        self._state = None
        self.poll()
