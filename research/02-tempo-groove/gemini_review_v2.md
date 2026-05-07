Ripgrep is not available. Falling back to GrepTool.
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:45:07 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=1224',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'ef654f8d1a20c926',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 2 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:45:11 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=420',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'abce8f52167957ec',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 3 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:45:25 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=715',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'a10395861f140ace',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 4 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:45:50 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=575',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '3c9b1a2eddff644f',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 5 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:46:12 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=1077',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '76f99a89a4f041de',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 6 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:46:52 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=1130',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '402113f9c31748cc',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 7 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:47:23 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=975',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'aa73e87625c23724',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
Attempt 8 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:8805:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:10768:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272574:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:272374:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:273221:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:250128:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:270322:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292938:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-SZYCJREE.js:292776:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.40.0/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/22.16.0'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Thu, 07 May 2026 16:47:58 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=1104',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'bb8318422c2e787',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  [Symbol(gaxios-gaxios-error)]: '6.7.1'
}
