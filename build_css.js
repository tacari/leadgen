
const execSync = require('child_process').execSync;

try {
  console.log('Building Tailwind CSS...');
  execSync('npx tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css');
  console.log('Tailwind CSS built successfully!');
} catch (error) {
  console.error('Error building Tailwind CSS:', error);
}
