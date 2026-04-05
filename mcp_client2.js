const { spawn } = require('child_process');
const server = spawn('npx', ['-y', '@21st-dev/magic@latest', '--stdio'], {
  env: { ...process.env, API_KEY: 'an_sk_aa5877ab1f8ffc5b55930b2aa639f5bb35695ec7ae0119f464bc791e28332f22' }
});

let messageId = 0;
function sendRpc(method, params = {}) {
  server.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: ++messageId, method, params }) + '\n');
}

server.stdout.on('data', (data) => {
  const lines = data.toString().split('\n').filter(Boolean);
  for (const line of lines) {
    try {
      const resp = JSON.parse(line);
      if (resp.id === 1) {
        sendRpc('tools/call', {
          name: 'logo_search',
          arguments: { queries: ["Apple"], format: "JSX" }
        });
      } else if (resp.id === 2) {
        console.log("\n--- LOGO SEARCH RESULT ---");
        resp.result.content.forEach(c => console.log(c.text));
        console.log("----------------------------\n");
        process.exit(0);
      }
    } catch (e) {}
  }
});

sendRpc('initialize', {
  protocolVersion: '2024-11-05',
  capabilities: {},
  clientInfo: { name: 'test-client', version: '1.0.0' }
});
