"""P0 production-load-order regression for the i18n bundle split.

Production load order is: static/i18n_shared.js (parser-blocking) → the
index.html bootstrap document.writes the saved locale bundle → deferred
static/i18n.js. Locale bundle top-level VALUES reference shared helpers
(e.g. pl.js: processed_elapsed: _i18nProcessedElapsedPl), so a bundle that
evaluates before i18n_shared.js throws ReferenceError and the locale never
registers — saved non-en users silently get English and the dropdown lists
only loaded locales.

The harness loads the scripts in production order. A missing
i18n_shared.js is tolerated (pre-fix tree) so the failure surfaces as the
real ReferenceError from bundle evaluation, not a missing-file error.
"""
import json
import pathlib
import shutil
import subprocess
import textwrap

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not available"
)


def test_locale_bundle_loads_in_production_order():
    script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const paths = [
          {json.dumps(str(REPO_ROOT / "static" / "i18n_shared.js"))},
          {json.dumps(str(REPO_ROOT / "static" / "i18n" / "pl.js"))},
          {json.dumps(str(REPO_ROOT / "static" / "i18n.js"))},
        ].filter((p) => fs.existsSync(p));
        const storage = {{}};
        const ctx = {{
          window: {{}},
          localStorage: {{
            getItem: (k) => Object.prototype.hasOwnProperty.call(storage, k) ? storage[k] : null,
            setItem: (k, v) => {{ storage[k] = String(v); }},
          }},
          document: {{
            documentElement: {{ lang: '' }},
            querySelectorAll: () => [],
          }},
        }};
        vm.createContext(ctx);
        for (const p of paths) {{
          try {{
            vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, {{ filename: p }});
          }} catch (err) {{
            process.stderr.write('EVAL_ERROR ' + p + ': ' + err.message + '\\n');
            process.exit(1);
          }}
        }}
        const out = vm.runInContext(`(() => {{
          const locale = window.LOCALES && window.LOCALES.pl;
          if (!locale || typeof locale !== 'object') {{
            return {{ ok: false, why: 'window.LOCALES.pl is not an object' }};
          }}
          if (typeof t !== 'function') {{
            return {{ ok: false, why: 't is not a function after static/i18n.js' }};
          }}
          let v = t('processed_elapsed');
          if (typeof v === 'function') v = v('2m');
          if (typeof v !== 'string' || v === 'processed_elapsed') {{
            return {{ ok: false, why: 'helper-mediated processed_elapsed unresolved: ' + JSON.stringify(v) }};
          }}
          return {{ ok: true, processedElapsed: v }};
        }})()`, ctx);
        if (!out.ok) {{
          process.stderr.write('ASSERT ' + out.why + '\\n');
          process.exit(1);
        }}
        process.stdout.write(JSON.stringify(out));
        """
    )
    proc = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    result = json.loads(proc.stdout)
    assert result["ok"] is True, result
