const vm = require('vm'); const fs = require('fs'); try { new vm.Script(fs.readFileSync('temp.js', 'utf8')); } catch(e) { console.log(e); }
