import { describe, it, expect, vi } from 'vitest';
import { createLogger, parseCaller } from '../../../static/js/modules/logger.js';

describe('logger.js', () => {
  it('createLogger derives the module name from the URL basename', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    const fileLogger = createLogger('file:///repo/static/js/modules/tag-manager.js');
    const httpLogger = createLogger('http://localhost/static/js/modules/slugify.js');
    const emptyLogger = createLogger();

    fileLogger.info('ping');
    expect(infoSpy).toHaveBeenLastCalledWith('[tag-manager] ping');

    httpLogger.info('ping');
    expect(infoSpy).toHaveBeenLastCalledWith('[slugify] ping');

    emptyLogger.info('ping');
    expect(infoSpy).toHaveBeenLastCalledWith('[module] ping');

    infoSpy.mockRestore();
  });

  it('maps levels to the right console methods with [name] msg format', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const logger = createLogger('file:///repo/static/js/modules/tag-manager.js');
    logger.info('info message');
    logger.warn('warn message');
    logger.error('error message');

    function debugCaller() {
      logger.debug('debug message');
    }
    debugCaller();

    expect(infoSpy).toHaveBeenCalledWith('[tag-manager] info message');
    expect(warnSpy).toHaveBeenCalledWith('[tag-manager] warn message');
    expect(errorSpy).toHaveBeenCalledWith('[tag-manager] error message');
    expect(debugSpy).toHaveBeenCalledWith(
      expect.stringMatching(/^\[tag-manager:\w+\] debug message$/)
    );

    debugSpy.mockRestore();
    infoSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  it('DEBUG includes the caller function; INFO+ carries no :fn segment', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    const logger = createLogger('file:///repo/static/js/modules/tag-manager.js');

    function callerFunction() {
      logger.debug('debug from a named function');
    }
    callerFunction();

    expect(debugSpy).toHaveBeenCalledWith(
      expect.stringMatching(/^\[tag-manager:\w+\] debug from a named function$/)
    );

    logger.info('info message');
    expect(infoSpy).toHaveBeenCalledWith('[tag-manager] info message');
    expect(infoSpy.mock.calls[0][0]).not.toContain(':');

    debugSpy.mockRestore();
    infoSpy.mockRestore();
  });

  it('parseCaller: valid stack → function name; malformed input → null; never throws', () => {
    const validStack = [
      'Error',
      '    at Object.debug (file:///repo/static/js/modules/logger.js:15:28)',
      '    at Object.updateFilterHeader (file:///repo/static/js/modules/tag-manager.js:111:15)',
    ].join('\n');
    expect(parseCaller(validStack)).toBe('updateFilterHeader');

    expect(parseCaller('')).toBeNull();
    expect(parseCaller('garbage')).toBeNull();
    expect(parseCaller(null)).toBeNull();
    expect(parseCaller(undefined)).toBeNull();

    // Stack with no named frames
    const noNamedFrames = ['Error', '    at file:///repo/app.js:20:5'].join('\n');
    expect(parseCaller(noNamedFrames)).toBeNull();

    // Never throws on hostile input
    expect(() => parseCaller({})).not.toThrow();
  });

  it('debug degrades gracefully when the stack is unparseable', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const originalError = globalThis.Error;
    class DegradedError {
      get stack() {
        return 'garbage';
      }
    }
    globalThis.Error = DegradedError;

    try {
      const logger = createLogger('file:///repo/static/js/modules/tag-manager.js');
      logger.debug('no stack message');

      // parseCaller('garbage') → null → plain [name] msg, no :fn segment
      expect(debugSpy).toHaveBeenCalledWith('[tag-manager] no stack message');
    } finally {
      globalThis.Error = originalError;
      debugSpy.mockRestore();
    }
  });
});
