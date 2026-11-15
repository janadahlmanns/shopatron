# Shopatron

This little script navigates the REWE online shop (rewe.de) and adds the items of a shopping
list to your cart. It never orders anything: once the list is done, the cart is left open for
you to review and check out yourself.

For every item, Shopatron remembers a default product. Items with a default go straight into
the cart. For items without one, the REWE search results page opens, you put the right product
into the cart yourself, and Shopatron asks whether to save it as the default for next time.

## Setup

You need Windows, Google Chrome and Python 3.10 or newer.

```
git clone <this repository>
cd shopatron
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No configuration files and no stored credentials are needed. You log in to REWE by hand in a
browser window, and Shopatron uses that session. Your market and pickup/delivery choice are
taken from your REWE account.

If Chrome is installed in an unusual location, adjust `CHROME_CANDIDATES` in `start_browser.py`.

## Running

1. Start the Shopatron browser:

   ```
   .venv\Scripts\python.exe start_browser.py
   ```

   A Chrome window opens with its own profile (separate from your normal Chrome). Log in to
   your REWE account there and choose your market. Leave this Chrome window open. The login
   is kept in the profile, so next time you are usually still logged in.

2. Start Shopatron:

   ```
   .venv\Scripts\python.exe -m shopatron
   ```

   Type or paste your shopping list, one item per line, and end it with an empty line.
   You can also put the list in a text file and pass the file name instead
   (see `example_list.txt`):

   ```
   .venv\Scripts\python.exe -m shopatron example_list.txt
   ```

### Shopping list format

| Line | Meaning |
|---|---|
| `Milch` | 1 × the default product for "Milch" |
| `Milch 5`, `5 Milch`, `5x Milch`, `Milch x5` | 5 × the default product |
| `Parmesan 80g`, `2 Sahne 200 ml` | amounts with a unit are not searched for; they are shown as a reminder while you pick the product |
| `Milch 5 ?` (or `? Milch 5`, `Milch 5 -`) | ignore the default this time and pick the product yourself |
| `# anything` | comment, ignored |

The quantity always means how many units of the REWE product go into the cart. Item names are
matched without regard to upper/lower case.

## What happens

For each item on the list:

- **Default product saved:** it is added to the cart in the given quantity, on top of
  anything already in the cart.
- **No default, default not available, or `?` marker:** the REWE search results for the item
  open in the browser. Click "add to cart" on the product you want. You can also search for
  something else with REWE's search box. Shopatron notices the product, sets the quantity from
  your list, and a small box in the corner of the page asks whether to save it as the default.
  "No" buys it just this once and keeps the old default. "Skip" leaves the item out.

At the end, the cart page opens with a summary (close it with ×). Review the cart and place
the order yourself.

To see all saved defaults:

```
.venv\Scripts\python.exe -m shopatron --defaults
```

Defaults are stored in `shopatron.db` in the project folder. It is personal data and is not
part of the repository.

## Notes

- Shopatron uses the REWE website the same way your browser does when you click through it,
  slowly and only for your own cart. REWE has no public API, so a change to their website can
  break it. `tools/watch_network.py` records what the website does, which helps when adapting
  Shopatron.
- Run the tests with `.venv\Scripts\python.exe -m pytest`.

## Future plans

- Receiving items to shop for through Siri commands, running on a home server (Raspberry Pi)
- A database of recipes with their ingredient lists
- A kitchen staples list to check the pantry against

## License

MIT, see [LICENSE](LICENSE).
