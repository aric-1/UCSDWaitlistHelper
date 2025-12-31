const form = document.getElementById("query-form");
const output = document.getElementById("output");

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const courseCode = document.getElementById("course").value.trim();
  const waitlistPos = Number(document.getElementById("waitlist").value);
  const capacityInput = Number(document.getElementById("capacity").value);
  const secondPassDate = document.getElementById("second-pass").value;

  if (!Number.isFinite(waitlistPos) || waitlistPos <= 0) {
    output.textContent = "Please enter a valid waitlist position (>= 1).";
    return;
  }
  if (!Number.isFinite(capacityInput) || capacityInput <= 0) {
    output.textContent = "Please enter a valid section capacity (>= 1).";
    return;
  }

  // Force time = 00:00 local time
  const secondPassISO = new Date(`${secondPassDate}T00:00:00`).toISOString();

  output.textContent = "Loading...";

  try {
    const res = await fetch(`${BACKEND_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        course_code: courseCode,
        second_pass_open: secondPassISO,
      }),
    });

    if (!res.ok) {
      throw new Error(`Backend error: ${res.status}`);
    }

    const data = await res.json();

    const sections = Array.isArray(data.sections) ? data.sections : [];
    // filter out entries without numeric capacity or drops_after
    const usable = sections.filter(s => Number.isFinite(s.capacity) && s.capacity > 0 && Number.isFinite(s.drops_after));

    if (usable.length === 0) {
      output.textContent = `Found ${sections.length} sections, but none had usable capacity/drops data to analyze.`;
      return;
    }

    const normalized = usable.map(s => {
      const scaled = s.drops_after * (capacityInput / s.capacity);
      return {...s, scaled_drops: scaled};
    });

    const avg_movement = normalized.reduce((acc, s) => acc + s.scaled_drops, 0) / normalized.length;
    const avg_margin = avg_movement - waitlistPos;
    const successes = normalized.filter(s => s.scaled_drops >= waitlistPos).length;

    const avg_movement_rounded = Math.round(avg_movement * 10) / 10;
    const avg_margin_rounded = Math.round(avg_margin * 10) / 10;

    const got_in_text = avg_margin >= 0 ? `would have gotten into ${courseCode}` : `would not have gotten into ${courseCode}`;
    const margin_abs = Math.abs(avg_margin_rounded);

    // Build a safe DOM summary and bold the key "got_in_text" part
    const summaryDiv = document.createElement('div');
    const p = document.createElement('p');
    p.appendChild(document.createTextNode(`We found ${normalized.length} sections in our database for your class. \n`));
    p.appendChild(document.createTextNode(`The waitlist moved an average ${avg_movement_rounded} positions from this time, meaning you `));

    const strong = document.createElement('strong');
    strong.textContent = got_in_text;
    p.appendChild(strong);

    p.appendChild(document.createTextNode(` by an average margin of ${margin_abs} spots. \n`));
    p.appendChild(document.createTextNode(`In ${successes} out of ${normalized.length} past sections, you would have made it.`));

    summaryDiv.appendChild(p);

    // Build formatted sections list
    const sectionsDiv = document.createElement('div');
    const h2 = document.createElement('h2');
    h2.textContent = 'Sections:';
    sectionsDiv.appendChild(h2);
    const ul = document.createElement('ul');
    normalized.forEach(s => {
      const count = Number.isFinite(s.drops_after) ? Math.round(s.drops_after) : (Number.isFinite(s.scaled_drops) ? Math.round(s.scaled_drops) : 0);
      const capText = Number.isFinite(s.capacity) ? ` (${s.capacity})` : '';
      const text = `${s.quarter}, Section ${s.section}${capText}: ${count} ${count === 1 ? 'opening' : 'openings'}`;
      const li = document.createElement('li');
      li.textContent = text;
      ul.appendChild(li);
    });
    sectionsDiv.appendChild(ul);

    // Clear previous output and append new nodes
    output.innerHTML = '';
    output.appendChild(summaryDiv);
    output.appendChild(sectionsDiv);
  } catch (err) {
    output.textContent = `Error: ${err.message}`;
  }
});