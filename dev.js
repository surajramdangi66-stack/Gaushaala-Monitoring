const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Candidate Python interpreter paths
const candidatePythons = [
  'C:\\Users\\rajen\\miniconda3\\python.exe',
  process.env.PYTHON,
  'python',
  'python3',
  'py'
].filter(Boolean);

function findPython() {
  for (const py of candidatePythons) {
    if (py.includes('\\') || py.includes('/')) {
      if (fs.existsSync(py)) {
        return py;
      }
    } else {
      return py;
    }
  }
  return 'python';
}

const pythonExe = findPython();
const args = process.argv.slice(2);

console.log('\n================================================================');
console.log('  🐄 SMART GAUSHALA CCTV AI LIVESTOCK SURVEILLANCE PLATFORM');
console.log('  🌐 Web & Dev Server Mode: http://localhost:8000');
console.log(`  ⚡ Runtime Python Engine: ${pythonExe}`);
console.log('================================================================\n');

let targetArgs = ['-B', 'run.py'];
if (args.includes('--test')) {
  targetArgs = ['-m', 'unittest', 'discover', '-s', 'backend/tests', '-p', '*.py'];
}

const child = spawn(pythonExe, targetArgs, {
  stdio: 'inherit',
  cwd: __dirname
});

child.on('error', (err) => {
  console.error('[Runner Error] Failed to start Gaushala CCTV system:', err);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code || 0);
});
