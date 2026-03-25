let recorder, stream, analyser, animId, timer, recSecs = 0, chunks = [], uploadedFile = null;

async function startRec() {
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { return showErr("Microphone access denied."); }

  clearInputWarning(); // Clear any previous warnings
  
  // Hide upload elements if a recording is started
  document.getElementById('dropzone').style.display = 'none';
  document.getElementById('upload-submit-button').style.display = 'none';
  document.getElementById('file-name-display').textContent = '';
  uploadedFile = null;

  // Visualiser
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  analyser = ctx.createAnalyser(); analyser.fftSize = 256;
  src.connect(analyser);
  document.getElementById('waveWrap').classList.add('on');
  drawWave();

  recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
  chunks = [];
  recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = () => {
    const contextInput = document.getElementById('ctx');
    if (!contextInput.value.trim()) {
        showInputWarning('Product context is required to submit a recording.');
        // Re-enable start button to allow user to try again after filling the context
        document.getElementById('startBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true; // Also disable stop button again
        return; 
    }
    submit(new Blob(chunks, { type: 'audio/webm' }), 'recording.webm');
  };
  recorder.start(100);

  document.getElementById('startBtn').disabled = true;
  document.getElementById('stopBtn').disabled  = false;
  document.getElementById('recInd').classList.add('on');
  recSecs = 0;
  timer = setInterval(() => {
    recSecs++;
    document.getElementById('recTime').textContent =
      Math.floor(recSecs/60) + ':' + String(recSecs%60).padStart(2,'0');
  }, 1000);
}

function stopRec() {
  recorder?.stop();
  stream?.getTracks().forEach(t => t.stop());
  clearInterval(timer);
  cancelAnimationFrame(animId);
  document.getElementById('recInd').classList.remove('on');
  document.getElementById('startBtn').disabled = false;
  document.getElementById('stopBtn').disabled  = true;
}

function drawWave() {
  const canvas = document.getElementById('waveform');
  const c = canvas.getContext('2d');
  const buf = new Uint8Array(analyser.frequencyBinCount);
  (function loop() {
    animId = requestAnimationFrame(loop);
    analyser.getByteTimeDomainData(buf);
    c.fillStyle = '#171726'; c.fillRect(0,0,canvas.width,canvas.height);
    c.strokeStyle = '#7c6eff'; c.lineWidth = 2; c.beginPath();
    const step = canvas.width / buf.length;
    buf.forEach((v, i) => {
      const y = (v/128) * canvas.height / 2;
      i ? c.lineTo(i*step, y) : c.moveTo(0, y);
    });
    c.stroke();
  })();
}

function handleFileUpload(file) {
    if (file && file.type.startsWith('audio/')) {
        uploadedFile = file;
        document.getElementById('file-name-display').textContent = `File: ${file.name}`;
        
        // Hide recording controls and show the upload submit button
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'none';
        document.getElementById('recInd').classList.remove('on');
        document.getElementById('upload-submit-button').style.display = 'inline-block';
        
        clearErr();
        clearInputWarning(); // Clear context warnings when a file is chosen
    } else {
        showErr('Please upload a valid audio file (mp3, wav, webm, etc.).');
    }
}

function analyzeUploadedFile() {
    const contextInput = document.getElementById('ctx');
    if (!contextInput.value.trim()) {
        showInputWarning('Product context is required to submit an uploaded file.');
        return;
    }
    if (uploadedFile) {
        submit(uploadedFile, uploadedFile.name);
    } else {
        showErr('No file has been uploaded.'); // This is a general error, so showErr is fine
    }
}


function onFile(e)  { handleFileUpload(e.target.files[0]); }
function onDrop(e)  {
  e.preventDefault(); document.getElementById('dropzone').classList.remove('over');
  handleFileUpload(e.dataTransfer.files[0]);
}

async function submit(blob, name) {
  clearErr();
  clearInputWarning();
  document.getElementById('loader').classList.add('on');
  document.getElementById('dropzone').style.display = 'none';
  document.getElementById('upload-submit-button').style.display = 'none';

  const fd = new FormData();
  fd.append('audio', blob, name);
  const contextInput = document.getElementById('ctx');
  fd.append('product_context', contextInput.value);

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { 
      document.getElementById('loader').classList.remove('on');
      showErr(data.error); 
      document.getElementById('dropzone').style.display=''; 
      return; 
    }
    window.currentAnalysis = data.analysis;
    setTimeout(() => {
      document.getElementById('loader').classList.remove('on');
      render(data.analysis);
      contextInput.value = ''; // Clear the textarea
      const element = document.querySelector('results');
      element.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, 600);
  } catch(e) {
    document.getElementById('loader').classList.remove('on');
    showErr('Network error: ' + e.message);
    document.getElementById('dropzone').style.display = '';
  }
}

function render(a) {
  document.getElementById('recSection').style.display = 'none';
  document.getElementById('results').style.display = 'block';
  document.getElementById('try-again-container').style.display = 'block'; // Show Try Again button

  // Score ring
  const score = a.overall_score ?? 0;
  const circ  = 377;
  const col   = score >= 75 ? '#3ee8a0' : score >= 50 ? '#fbbf24' : '#ff6b8a';
  const fill  = document.getElementById('ringFill');
  setTimeout(() => { fill.style.strokeDashoffset = circ - (score/100)*circ; }, 80);
  fill.style.stroke = col;
  document.getElementById('ringNum').textContent = score;
  document.getElementById('ringNum').style.color = col;

  document.getElementById('impression').textContent = a.overall_impression ?? '';

  const en = (a.energy_level ?? 'medium').toLowerCase();
  const eb = document.getElementById('energyBadge');
  eb.textContent = '⚡ ' + en.charAt(0).toUpperCase() + en.slice(1) + ' Energy';
  eb.className = 'badge badge-' + en;

  document.getElementById('nextFocus').textContent = a.next_practice_focus ?? '';

  // Dimensions
  const dimLabels = {
    clarity:          'Clarity',
    tone_confidence:  'Tone & Confidence',
    pacing:           'Pacing',
    product_knowledge:'Product Knowledge',
    persuasiveness:   'Persuasiveness',
    vocabulary:       'Vocabulary',
  };
  const dims = document.getElementById('dims');
  dims.innerHTML = '';
  for (const [k, label] of Object.entries(dimLabels)) {
    const d  = (a.dimensions ?? {})[k] ?? {};
    const sc = d.score ?? 0;
    const c  = sc >= 75 ? '#3ee8a0' : sc >= 50 ? '#fbbf24' : '#ff6b8a';
    dims.innerHTML += `
      <div class="dim" title="${d.feedback ?? ''}">
        <div class="dim-row">
          <span class="dim-name">${label}</span>
          <span class="dim-sc" style="color:${c}">${sc}</span>
        </div>
        <div class="bar"><div class="bar-fill" style="width:0%;background:${c}" data-w="${sc}%"></div></div>
      </div>`;
  }
  setTimeout(() => { document.querySelectorAll('.bar-fill').forEach(el => el.style.width = el.dataset.w); }, 150);

  document.getElementById('transcript').textContent = a.transcript ?? 'No transcript available.';

  document.getElementById('strengths').innerHTML =
    (a.strengths ?? []).map(s => `<span class="tag tag-g">✓ ${s}</span>`).join('');

  const fw = a.filler_words ?? {};
  document.getElementById('fillerNote').textContent =
    `Detected ${fw.count ?? 0} filler occurrence(s). ${fw.feedback ?? ''}`;
  document.getElementById('fillerTags').innerHTML =
    (fw.words ?? []).slice(0, 15).map(w => `<span class="tag tag-y">${w}</span>`).join('');

  document.getElementById('improvements').innerHTML =
    (a.improvements ?? []).map(i => `
      <div class="imp-item">
        <h4>${i.issue}</h4>
        <p>${i.detail}</p>
        <div class="sug">💡 ${i.suggestion}</div>
      </div>`).join('');
}

function reset() {
  document.getElementById('results').style.display    = 'none';
  document.getElementById('recSection').style.display = 'block';
  document.getElementById('dropzone').style.display   = '';
  document.getElementById('fileInput').value          = '';
  document.getElementById('waveWrap').classList.remove('on');
  document.getElementById('try-again-container').style.display = 'none'; // Hide Try Again button
  
  // Reset UI for new submission
  uploadedFile = null;
  document.getElementById('file-name-display').textContent = '';
  document.getElementById('upload-submit-button').style.display = 'none';
  document.getElementById('startBtn').style.display = 'inline-block';
  document.getElementById('startBtn').disabled = false;
  document.getElementById('stopBtn').style.display = 'inline-block';
  document.getElementById('stopBtn').disabled = true;

  chunks = [];
}

async function downloadPDF() {
  const analysis = window.currentAnalysis;
  if (!analysis) {
    showErr('No analysis data available to generate a report.');
    return;
  }
  
  const downloadButton = document.querySelector('button[onclick="downloadPDF()"]');
  const originalButtonText = downloadButton.innerHTML;

  try {
    downloadButton.disabled = true;
    downloadButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Downloading...';

    const res = await fetch('/download_report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(analysis),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || 'Failed to generate PDF report');
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;

    // Get filename from Content-Disposition header
    const disposition = res.headers.get('Content-Disposition');
    let filename = 'Speech_Score_Analysis.pdf'; // default
    if (disposition && disposition.indexOf('attachment') !== -1) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) { 
          filename = matches[1].replace(/['"]/g, '');
        }
    }
    a.download = filename;
    
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

  } catch (error) {
    console.error('Error downloading PDF:', error);
    showErr(error.message);
  } finally {
    downloadButton.disabled = false;
    downloadButton.innerHTML = originalButtonText;
  }
}

function showErr(msg) { const e = document.getElementById('errBox'); e.textContent = msg; e.classList.add('on'); }
function clearErr()   { document.getElementById('errBox').classList.remove('on'); }

function showInputWarning(msg) {
  const warningEl = document.getElementById('input-warning');
  warningEl.textContent = msg;
  warningEl.style.display = 'block';
}

function clearInputWarning() {
  const warningEl = document.getElementById('input-warning');
  warningEl.style.display = 'none';
}
