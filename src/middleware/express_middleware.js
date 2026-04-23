'use strict';
/**
 * middleware/express_middleware.js — VigilAI drop-in middleware for Express apps.
 *
 * Captures every HTTP request and sends it to the VigilAI ingest server.
 * Uses only Node.js built-in modules (http/https) — no npm dependencies.
 *
 * Usage (3 lines):
 *   const { createVigilMiddleware } = require('./src/middleware/express_middleware');
 *   const app = express();
 *   app.use(createVigilMiddleware({ vigilUrl: 'http://localhost:9000/ingest' }));
 *
 * Options:
 *   vigilUrl       URL of the VigilAI ingest server  (default: http://localhost:9000/ingest)
 *   windowSeconds  Sliding-window length for per-key request counting  (default: 60)
 *
 * The request_count field is the cumulative count of requests for this api_key
 * within the current window — same semantics as fastapi_middleware.py.
 */

const http  = require('http');
const https = require('https');
const url   = require('url');

/**
 * @param {{ vigilUrl?: string, windowSeconds?: number }} [options]
 * @returns {import('express').RequestHandler}
 */
function createVigilMiddleware(options) {
    options = options || {};
    const vigilUrl      = options.vigilUrl      || 'http://localhost:9000/ingest';
    const windowSeconds = options.windowSeconds || 60;

    // { apiKey: { count: number, windowStart: number } }
    const _counters = {};

    function _getApiKey(req) {
        const xKey = req.headers['x-api-key'];
        if (xKey) return xKey;

        const auth = req.headers['authorization'] || '';
        if (auth.startsWith('Bearer ')) {
            const token = auth.slice('Bearer '.length).trim();
            if (token) return token;
        }

        try {
            const parsed = new url.URL(req.url, 'http://x');
            const qKey   = parsed.searchParams.get('api_key');
            if (qKey) return qKey;
        } catch (_) {}

        return 'anonymous';
    }

    function _increment(apiKey) {
        const now = Date.now() / 1000;
        if (!_counters[apiKey]) {
            _counters[apiKey] = { count: 0, windowStart: now };
        }
        const entry = _counters[apiKey];
        if (now - entry.windowStart >= windowSeconds) {
            entry.count       = 0;
            entry.windowStart = now;
        }
        entry.count += 1;
        return entry.count;
    }

    function _sendLog(log) {
        const body   = JSON.stringify(log);
        const parsed = new url.URL(vigilUrl);
        const lib    = parsed.protocol === 'https:' ? https : http;
        const opts   = {
            hostname: parsed.hostname,
            port:     parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
            path:     parsed.pathname,
            method:   'POST',
            headers: {
                'Content-Type':   'application/json',
                'Content-Length': Buffer.byteLength(body),
            },
        };
        const req = lib.request(opts);
        req.on('error', function() {});  // fire-and-forget: swallow all errors
        req.write(body);
        req.end();
    }

    return function vigilMiddleware(req, res, next) {
        const startNs = process.hrtime.bigint();

        res.on('finish', function() {
            const elapsedNs  = process.hrtime.bigint() - startNs;
            const latency    = parseFloat((Number(elapsedNs) / 1e9).toFixed(4));
            const apiKey     = _getApiKey(req);
            const count      = _increment(apiKey);

            const reqUrl = req.url || '/';
            let endpoint;
            try {
                endpoint = new url.URL(reqUrl, 'http://x').pathname;
            } catch (_) {
                endpoint = reqUrl.split('?')[0];
            }

            const now = new Date();
            const ts  = now.toISOString().replace('T', ' ').slice(0, 19);

            _sendLog({
                api_key:       apiKey,
                endpoint:      endpoint,
                method:        req.method,
                status_code:   res.statusCode,
                response_time: latency,
                ip_address:    req.ip || (req.socket && req.socket.remoteAddress) || 'unknown',
                timestamp:     ts,
                request_count: count,
                attack_type:   'real',
            });
        });

        next();
    };
}

module.exports = { createVigilMiddleware };
