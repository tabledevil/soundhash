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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:48:31 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=447',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '39c71bab272c25f1',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:48:38 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=318',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '922cc54f9e309447',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:48:49 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=381',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '221cef2c2c2530b5',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:49:10 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=346',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'd3a029fadeae4f5f',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:49:39 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=491',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '5fa9941e0d755307',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:50:17 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=439',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '3f428cc5d47b3a97',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:50:54 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7104',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'c0b656135dd14305',
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
    at Gaxios._request (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:8811:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async _OAuth2Client.requestAsync (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:10774:16)
    at async CodeAssistServer.requestStreamingPost (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272793:17)
    at async CodeAssistServer.generateContentStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:272591:23)
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:273444:19
    at async file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:250345:23
    at async retryWithBackoff (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:270539:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293199:28)
    at async GeminiChat.streamWithRetries (file:///Users/tabledevil/.nvm/versions/node/v22.16.0/lib/node_modules/@google/gemini-cli/bundle/chunk-6DSAZLFF.js:293037:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.41.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
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
      date: 'Fri, 08 May 2026 15:51:21 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=250',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '12e80ff7976a54f4',
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
