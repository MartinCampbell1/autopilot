const { spawn } = require('child_process');
const server = spawn('npx', ['-y', '@21st-dev/magic@latest', '--stdio'], {
  env: { ...process.env, API_KEY: 'an_sk_aa5877ab1f8ffc5b55930b2aa639f5bb35695ec7ae0119f464bc791e28332f22' }
});

let messageId = 0;

function sendRpc(method, params = {}) {
  const msg = { jsonrpc: '2.0', id: ++messageId, method, params };
  server.stdin.write(JSON.stringify(msg) + '\n');
}

server.stdout.on('data', (data) => {
  const lines = data.toString().split('\n').filter(Boolean);
  for (const line of lines) {
    try {
      const resp = JSON.parse(line);
      if (resp.method === 'window/logMessage') {
        console.log('[MCP LOG]', resp.params.message);
      } else {
        console.log('[MCP RESP]', JSON.stringify(resp).substring(0, 100) + '...');
      }
      
      if (resp.id === 1) { // initialized
        sendRpc('tools/list');
      } else if (resp.id === 2 && resp.result && resp.result.tools) {
        console.log("Calling 21st_magic_component_builder...");
        sendRpc('tools/call', {
          name: '21st_magic_component_builder',
          arguments: {
            message: "Generate a lightweight fast login button",
            searchQuery: "login button react tailwind",
            absolutePathToCurrentFile: "/Users/example/Desktop/autopilot/src/components/LoginForm.tsx",
            absolutePathToProjectDirectory: "/Users/example/Desktop/autopilot",
            standaloneRequestQuery: "login button"
          }
        });
      } else if (resp.id === 3) {
        if (resp.result && resp.result.content) {
          console.log("\n--- COMPONENT GENERATION RESULT ---");
          resp.result.content.forEach(c => console.log(c.text));
          console.log("----------------------------------\n");
        } else {
          console.log("Error or empty result:", JSON.stringify(resp, null, 2));
        }
        process.exit(0);
      }
    } catch (e) {
      if (!line.includes('Content-Length')) {
        console.log('[RAW OUT]', line);
      }
    }
  }
});

server.stderr.on('data', (data) => {
  console.error('stderr:', data.toString());
});

sendRpc('initialize', {
  protocolVersion: '2024-11-05',
  capabilities: {},
  clientInfo: { name: 'test-client', version: '1.0.0' }
});
