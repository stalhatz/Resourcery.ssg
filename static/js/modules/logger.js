/**
 * Console-only logger for Resourcery.ssg frontend modules.
 *
 * Browsers have no stdout/stderr/log files, so this is a thin level→console
 * mapper with module identity derived from import.meta.url (no INFO_USER
 * level — that exists only for the Python console/file split). DEBUG is the
 * only level that parses the stack (for the caller function name): stack
 * parsing is non-standard across engines and is confined to the debug
 * method, wrapped so it never throws.
 *
 * @param {string} moduleUrl — import.meta.url of the consuming module.
 * @returns {{debug: Function, info: Function, warn: Function, error: Function}}
 */

/**
 * Extract a function name from a single v8-style stack frame line, e.g.
 * "    at Object.updateFilterHeader (file:///…:40:19)". Anonymous frames
 * (no named function) return null.
 *
 * @param {string} line
 * @returns {string|null}
 */
function extractFunctionName(line) {
  const match = line.match(
    /at\s+(?:Object\.|async\s+)?([A-Za-z_$][\w$]*)\s*(?:\(|$)/
  );
  return match ? match[1] : null;
}

/**
 * Parse a raw stack string and return the name of the caller function —
 * the first named frame below the logger's own method frame. Best-effort:
 * any malformed or unexpected stack shape degrades to null, never throws.
 *
 * @param {string} stack — raw Error().stack string.
 * @returns {string|null}
 */
export function parseCaller(stack) {
  try {
    if (typeof stack !== 'string') {
      return null;
    }
    const lines = stack.split('\n');
    for (let i = 1; i < lines.length; i += 1) {
      const name = extractFunctionName(lines[i]);
      if (name && name !== 'debug') {
        return name;
      }
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Create a logger for a module. The module name is the basename of the
 * module URL without the .js suffix; a missing/malformed URL degrades to
 * "module".
 *
 * @param {string} moduleUrl
 * @returns {{debug: Function, info: Function, warn: Function, error: Function}}
 */
export function createLogger(moduleUrl) {
  let name = 'module';
  try {
    if (typeof moduleUrl === 'string') {
      const basename = moduleUrl.split('/').pop();
      if (basename) {
        name = basename.replace(/\.js$/, '');
      }
    }
  } catch {
    name = 'module';
  }

  const format = (fn, msg) => `[${name}${fn ? ':' + fn : ''}] ${msg}`;

  return {
    debug(msg) {
      const fn = parseCaller(new Error().stack);
      console.debug(format(fn, msg));
    },
    info(msg) {
      console.info(format(null, msg));
    },
    warn(msg) {
      console.warn(format(null, msg));
    },
    error(msg) {
      console.error(format(null, msg));
    },
  };
}
