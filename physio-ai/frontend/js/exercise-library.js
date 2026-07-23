/**
 * PhysioAI — Exercise Library Dataset & Interactive Renderer
 * 
 * Provides comprehensive exercise categories, individual routines, search filtering,
 * category detail rendering, and exercise session preview modals.
 */

const EXERCISE_CATEGORIES = [
  {
    id: "hand-rehabilitation",
    title: "Hand & Finger Rehabilitation",
    group: "Fine Motor",
    description: "Gentle exercises to restore dexterity, fine pinch strength, and smooth finger mobility.",
    image: "assets/images/categories/hand-rehabilitation.svg",
    exercisesCount: 7,
    featured: false,
    exercises: [
      { name: "Finger Flexion", target: "Digital Flexor Tendons", duration: "4 - 6 mins", difficulty: "Gentle", desc: "Slow, controlled curling of fingers into a soft fist to restore movement range." },
      { name: "Finger Extension", target: "Extensor Digitorum", duration: "5 mins", difficulty: "Gentle", desc: "Gentle outward spreading of fingers against mild resistance." },
      { name: "Tendon Gliding", target: "Flexor Digitorum Superficialis", duration: "6 - 8 mins", difficulty: "Gentle", desc: "Sequential hand positions (hook, straight fist, full fist) for tendon smoothness." },
      { name: "Thumb Opposition", target: "Opponens Pollicis", duration: "5 mins", difficulty: "Gentle", desc: "Touching the thumb tip sequentially to each fingertip with gentle precision." },
      { name: "Pinch Grip Training", target: "Intrinsic Hand Muscles", duration: "5 mins", difficulty: "Moderate", desc: "Isometric pinch holding to rebuild functional key and fingertip grip strength." },
      { name: "Wrist Mobility", target: "Carpal Joint Complex", duration: "6 mins", difficulty: "Gentle", desc: "Soft circular movements to relieve joint stiffness and restore fluid hand movement." },
      { name: "Grip Strength", target: "Forearm & Palmar Flexors", duration: "7 mins", difficulty: "Moderate", desc: "Squeezing a soft therapy ball to safely build functional hand strength." }
    ]
  },
  {
    id: "wrist-forearm",
    title: "Wrist & Forearm",
    group: "Upper Body",
    description: "Targeted flexor and extensor movements to ease wrist tension and rebuild arm stability.",
    image: "assets/images/categories/wrist-forearm.svg",
    exercisesCount: 5,
    featured: false,
    exercises: [
      { name: "Wrist Flexion", target: "Flexor Carpi Radialis", duration: "5 mins", difficulty: "Gentle", desc: "Controlled downward bending of the wrist supported over a soft surface." },
      { name: "Wrist Extension", target: "Extensor Carpi Radialis", duration: "5 mins", difficulty: "Gentle", desc: "Upward bending motion to strengthen the back of the wrist and forearm." },
      { name: "Wrist Rotation", target: "Radiocarpal Joint", duration: "6 mins", difficulty: "Gentle", desc: "Smooth clockwise and counter-clockwise rotations for joint lubrication." },
      { name: "Forearm Pronation", target: "Pronator Teres", duration: "5 mins", difficulty: "Moderate", desc: "Turning palm downward in a slow, controlled therapeutic motion." },
      { name: "Forearm Supination", target: "Supinator & Biceps", duration: "5 mins", difficulty: "Moderate", desc: "Rotating palm upward to restore complete forearm rotational freedom." }
    ]
  },
  {
    id: "shoulder-rehabilitation",
    title: "Shoulder Rehabilitation",
    group: "Upper Body",
    description: "Rebuild comfortable overhead reach, rotator cuff resilience, and scapular stability.",
    image: "assets/images/categories/shoulder-rehabilitation.svg",
    exercisesCount: 5,
    featured: true,
    exercises: [
      { name: "Shoulder Abduction", target: "Middle Deltoid & Supraspinatus", duration: "6 - 8 mins", difficulty: "Moderate", desc: "Lifting the arm out to the side in a smooth, painless arc of movement." },
      { name: "Shoulder Flexion", target: "Anterior Deltoid", duration: "6 mins", difficulty: "Gentle", desc: "Raising arm forward and upward toward comfortable eye height." },
      { name: "External Rotation", target: "Infraspinatus & Teres Minor", duration: "7 mins", difficulty: "Moderate", desc: "Rotating arm outward with elbow tucked at 90 degrees to reinforce rotator cuff." },
      { name: "Internal Rotation", target: "Subscapularis", duration: "6 mins", difficulty: "Gentle", desc: "Controlled inward rotation across the torso for balanced shoulder alignment." },
      { name: "Wall Slides", target: "Scapular Stabilizers", duration: "8 mins", difficulty: "Active", desc: "Gliding forearms up a wall while keeping shoulder blades engaged." }
    ]
  },
  {
    id: "elbow-rehabilitation",
    title: "Elbow Rehabilitation",
    group: "Upper Body",
    description: "Restore complete elbow extension, smooth flexion, and surrounding arm comfort.",
    image: "assets/images/categories/elbow-rehabilitation.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Elbow Flexion", target: "Brachialis & Biceps Brachii", duration: "5 mins", difficulty: "Gentle", desc: "Bending the arm smoothly bringing palm toward the shoulder." },
      { name: "Elbow Extension", target: "Triceps Brachii", duration: "5 mins", difficulty: "Gentle", desc: "Gentle straightening of the arm down to full comfortable extension." },
      { name: "Biceps Stretch", target: "Anterior Upper Arm", duration: "4 mins", difficulty: "Gentle", desc: "Soft lengthening stretch across the elbow fold and upper arm." },
      { name: "Triceps Stretch", target: "Posterior Upper Arm", duration: "4 mins", difficulty: "Gentle", desc: "Overhead elbow bend stretch to release tension along the back of the arm." }
    ]
  },
  {
    id: "neck-mobility",
    title: "Neck Mobility",
    group: "Upper Body",
    description: "Calming cervical stretches designed to ease upper back tightness and improve rotation.",
    image: "assets/images/categories/neck-mobility.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Neck Rotation", target: "Sternocleidomastoid", duration: "4 - 5 mins", difficulty: "Gentle", desc: "Slow side-to-side head turns staying well within comfort limits." },
      { name: "Chin Tucks", target: "Deep Cervical Flexors", duration: "5 mins", difficulty: "Gentle", desc: "Subtle backward chin draw to re-align head over spine posture." },
      { name: "Lateral Neck Stretch", target: "Upper Trapezius", duration: "4 mins", difficulty: "Gentle", desc: "Tilting ear gently toward shoulder to relieve side neck stiffness." },
      { name: "Cervical Mobility", target: "Suboccipitals & Spine", duration: "6 mins", difficulty: "Gentle", desc: "Rhythmic head nodding and tilting to enhance upper neck freedom." }
    ]
  },
  {
    id: "back-spine",
    title: "Back & Spine",
    group: "Core & Spine",
    description: "Spinal decompression, core stabilization, and gentle lumbar mobilization.",
    image: "assets/images/categories/back-spine.svg",
    exercisesCount: 5,
    featured: false,
    exercises: [
      { name: "Cat-Cow", target: "Thoracolumbar Spine", duration: "6 mins", difficulty: "Gentle", desc: "Alternating spinal arching and rounding on hands and knees for fluidity." },
      { name: "Bird Dog", target: "Multifidus & Core", duration: "8 mins", difficulty: "Moderate", desc: "Opposite arm and leg reach while maintaining a quiet, stable torso." },
      { name: "Pelvic Tilt", target: "Lower Abdominals & Lumbar", duration: "5 mins", difficulty: "Gentle", desc: "Flattening lower back gently against the floor to engage deep core." },
      { name: "Lumbar Extension", target: "Erector Spinae", duration: "6 mins", difficulty: "Gentle", desc: "Prone press-up stretch to relieve disc compression and restore extension." },
      { name: "Thoracic Rotation", target: "Mid-back Mobilizers", duration: "6 mins", difficulty: "Moderate", desc: "Sidelying open-book arm sweeps to open chest and mid-spine." }
    ]
  },
  {
    id: "hip-rehabilitation",
    title: "Hip Rehabilitation",
    group: "Lower Body",
    description: "Strengthen glutes, open hip flexors, and enhance pelvic alignment for comfortable walking.",
    image: "assets/images/categories/hip-rehabilitation.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Hip Abduction", target: "Gluteus Medius", duration: "6 mins", difficulty: "Moderate", desc: "Side-lying leg raise to bolster lateral pelvic balance." },
      { name: "Hip Extension", target: "Gluteus Maximus", duration: "6 mins", difficulty: "Moderate", desc: "Backward leg lift engaging gluteal muscles without arching lower back." },
      { name: "Hip Flexion", target: "Iliopsoas & Rectus Femoris", duration: "5 mins", difficulty: "Gentle", desc: "Seated or standing knee lift to encourage smooth stride flex." },
      { name: "Clamshell", target: "Deep Hip Rotators", duration: "7 mins", difficulty: "Moderate", desc: "Opening knees like a clamshell while keeping heels together." }
    ]
  },
  {
    id: "knee-rehabilitation",
    title: "Knee Rehabilitation",
    group: "Lower Body",
    description: "Rebuild quadriceps strength, patellar tracking, and knee extension mobility.",
    image: "assets/images/categories/knee-rehabilitation.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Straight Leg Raise", target: "Quadriceps Femoris", duration: "6 - 8 mins", difficulty: "Moderate", desc: "Lifting straight leg while lying down to build anterior knee stability." },
      { name: "Mini Squat", target: "Vastus Medialis & Glutes", duration: "7 mins", difficulty: "Moderate", desc: "Shallow, controlled knee bend keeping weight centered over heels." },
      { name: "Knee Extension", target: "Terminal Quads", duration: "5 mins", difficulty: "Gentle", desc: "Seated leg extension focusing on full comfortable knee lockout." },
      { name: "Hamstring Curl", target: "Posterior Thigh", duration: "6 mins", difficulty: "Gentle", desc: "Bending knee standing or lying to tone posterior leg stabilizers." }
    ]
  },
  {
    id: "ankle-foot",
    title: "Ankle & Foot",
    group: "Lower Body",
    description: "Improve balance foundation, ankle range of motion, and calf flexibility.",
    image: "assets/images/categories/ankle-foot.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Heel Raises", target: "Gastrocnemius & Soleus", duration: "5 mins", difficulty: "Moderate", desc: "Rising up onto ball of foot to rebuild calf strength and ankle stability." },
      { name: "Toe Raises", target: "Tibialis Anterior", duration: "5 mins", difficulty: "Gentle", desc: "Lifting toes off the floor to tone shin muscles and prevent tripping." },
      { name: "Ankle Circles", target: "Talocrural Joint", duration: "4 mins", difficulty: "Gentle", desc: "Smooth circular ankle tracing in the air to ease joint stiffness." },
      { name: "Balance Exercise", target: "Proprioceptors & Feet", duration: "6 mins", difficulty: "Moderate", desc: "Barefoot grounding balance holding to activate foot arch intrinsics." }
    ]
  },
  {
    id: "balance-stability",
    title: "Balance & Stability",
    group: "Full Body",
    description: "Enhance body awareness, fall prevention, and confidence during daily movements.",
    image: "assets/images/categories/balance-stability.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Single Leg Balance", target: "Proprioceptive System", duration: "5 - 7 mins", difficulty: "Moderate", desc: "Standing tall on one foot near a support surface to train ankle balance." },
      { name: "Tandem Standing", target: "Vestibular & Core Alignment", duration: "5 mins", difficulty: "Moderate", desc: "Standing heel-to-toe to challenge balance in a narrow base." },
      { name: "Weight Shift", target: "Center of Gravity", duration: "6 mins", difficulty: "Gentle", desc: "Gentle side-to-side and front-to-back weight transfer drills." },
      { name: "Stability Reach", target: "Functional Dynamic Balance", duration: "8 mins", difficulty: "Active", desc: "Reaching out in multiple planes while maintaining a steady stance." }
    ]
  },
  {
    id: "full-body-mobility",
    title: "Full Body Mobility",
    group: "Full Body",
    description: "Holistic morning routines and gentle stretching to energize all major joints.",
    image: "assets/images/categories/full-body-mobility.svg",
    exercisesCount: 4,
    featured: false,
    exercises: [
      { name: "Morning Mobility", target: "Whole Body System", duration: "10 mins", difficulty: "Gentle", desc: "Calm whole-body flow combining breath, spine flex, and shoulder rolls." },
      { name: "Dynamic Stretching", target: "Major Muscle Groups", duration: "8 mins", difficulty: "Moderate", desc: "Continuous fluid movement stretches to prepare body for daily activities." },
      { name: "Functional Reach", target: "Kinetic Chain", duration: "7 mins", difficulty: "Gentle", desc: "Gentle overhead and diagonal reaching to expand movement ease." },
      { name: "Posture Correction", target: "Postural Chain & Core", duration: "6 mins", difficulty: "Gentle", desc: "Scapular squeeze and pelvic reset drills for upright posture confidence." }
    ]
  }
];

document.addEventListener('DOMContentLoaded', () => {
  const categoryGrid = document.getElementById('category-grid');
  const exerciseList = document.getElementById('exercise-list');
  
  if (categoryGrid) {
    initLibraryPage(categoryGrid);
  }
  
  if (exerciseList) {
    initCategoryPage(exerciseList);
  }
});

/**
 * Initialize Browse Library Main Grid
 */
function initLibraryPage(gridEl) {
  let currentGroup = 'all';
  let searchQuery = '';

  function render() {
    const filtered = EXERCISE_CATEGORIES.filter(cat => {
      const matchesGroup = currentGroup === 'all' || cat.group.toLowerCase().includes(currentGroup) || cat.title.toLowerCase().includes(currentGroup);
      const matchesSearch = cat.title.toLowerCase().includes(searchQuery) ||
                            cat.description.toLowerCase().includes(searchQuery);
      return matchesGroup && matchesSearch;
    });

    if (filtered.length === 0) {
      gridEl.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--color-text-secondary);">
          <p style="font-size: 1.2rem; font-family: var(--font-serif); margin-bottom: 0.5rem;">No matching categories found</p>
          <p style="font-size: 0.95rem;">Try adjusting your search terms or selecting 'All'.</p>
        </div>
      `;
      return;
    }

    gridEl.innerHTML = filtered.map(cat => `
      <a href="exercise-category.html?category=${cat.id}" class="category-card" aria-label="${cat.title}">
        <div class="category-card-media">
          <img src="${cat.image}" alt="${cat.title} illustration" loading="lazy" />
          <span class="exercise-count-badge">${cat.exercisesCount} Exercises</span>
        </div>
        <div class="category-card-body">
          <h3 class="category-card-title">${cat.title}</h3>
          <p class="category-card-desc">${cat.description}</p>
          <div class="category-card-footer">
            <span>Explore collection</span>
            <span class="arrow" aria-hidden="true">→</span>
          </div>
        </div>
      </a>
    `).join('');
  }

  // Bind Search Input
  const searchInput = document.getElementById('category-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      render();
    });
  }

  // Bind Filter Chips
  const chips = document.querySelectorAll('.filter-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentGroup = chip.dataset.group || 'all';
      render();
    });
  });

  render();
}

/**
 * Initialize Category Details Page (`exercise-category.html`)
 */
function initCategoryPage(listEl) {
  const params = new URLSearchParams(window.location.search);
  const categoryId = params.get('category') || 'shoulder-rehabilitation';
  
  const category = EXERCISE_CATEGORIES.find(c => c.id === categoryId) || EXERCISE_CATEGORIES[2];

  // Update Page Metadata & Headers
  document.title = `${category.title} | PhysioAI`;
  
  const titleEl = document.getElementById('category-title');
  const descEl = document.getElementById('category-description');
  const countEl = document.getElementById('exercise-count');
  const artEl = document.getElementById('category-artwork');
  
  if (titleEl) titleEl.textContent = category.title;
  if (descEl) descEl.textContent = category.description;
  if (countEl) countEl.textContent = `${category.exercises.length} Exercises Available`;
  if (artEl) {
    artEl.innerHTML = `<img src="${category.image}" alt="${category.title}">`;
  }

  // Render Exercise Cards
  listEl.className = 'exercise-list-grid';
  listEl.innerHTML = category.exercises.map((ex) => {
    const diffClass = ex.difficulty.toLowerCase() === 'gentle' ? 'difficulty-gentle' :
                      ex.difficulty.toLowerCase() === 'moderate' ? 'difficulty-moderate' : 'difficulty-active';
    
    return `
      <article class="exercise-card">
        <div class="exercise-card-header">
          <h3 class="exercise-card-title">${ex.name}</h3>
          <span class="difficulty-pill ${diffClass}">${ex.difficulty}</span>
        </div>
        <div class="exercise-card-details">
          <div class="detail-item">⏱ <span>${ex.duration}</span></div>
          <div class="detail-item">🎯 <span>${ex.target}</span></div>
        </div>
        <p class="exercise-card-desc">${ex.desc}</p>
        <button class="btn-start-exercise" onclick="openExercisePreview('${ex.name.replace(/'/g, "\\'")}', '${category.title.replace(/'/g, "\\'")}', '${ex.duration}', '${ex.target.replace(/'/g, "\\'")}')">
          <span>Start Exercise</span>
          <span aria-hidden="true">→</span>
        </button>
      </article>
    `;
  }).join('');
}

/**
 * Exercise Preview Modal handler
 */
function openExercisePreview(name, categoryName, duration, target) {
  let modalOverlay = document.getElementById('exerciseModal');
  if (!modalOverlay) {
    modalOverlay = document.createElement('div');
    modalOverlay.id = 'exerciseModal';
    modalOverlay.className = 'exercise-modal-overlay';
    document.body.appendChild(modalOverlay);
  }

  modalOverlay.innerHTML = `
    <div class="exercise-modal-content">
      <button class="modal-close-btn" onclick="closeExercisePreview()" aria-label="Close modal">✕</button>
      <p style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-accent); font-weight: 700; margin-bottom: 0.5rem;">${categoryName}</p>
      <h2 style="font-family: var(--font-serif); font-size: 2.25rem; color: var(--color-primary); margin-bottom: 0.75rem;">${name}</h2>
      
      <div style="display: flex; gap: 1.5rem; background-color: var(--color-bg-subtle); padding: 1rem 1.25rem; border-radius: var(--radius-md); margin-bottom: 1.5rem; font-size: 0.9rem;">
        <div><strong>Duration:</strong> ${duration}</div>
        <div><strong>Target Area:</strong> ${target}</div>
      </div>

      <div style="background: linear-gradient(135deg, var(--color-primary) 0%, #162E28 100%); color: #FFFFFF; padding: 2.5rem 1.5rem; border-radius: var(--radius-lg); text-align: center; margin-bottom: 1.5rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🌿</div>
        <h4 style="font-family: var(--font-serif); font-weight: 400; font-size: 1.35rem; margin-bottom: 0.35rem;">Guided Session Ready</h4>
        <p style="font-size: 0.9rem; color: rgba(255,255,255,0.85); font-weight: 300;">Position yourself comfortably in front of your camera when you are ready to begin.</p>
      </div>

      <div style="display: flex; gap: 1rem;">
        <button class="btn-start-exercise" style="flex: 1;" onclick="alert('Session started! Guided movement tracking active.'); closeExercisePreview();">Begin Movement</button>
        <button class="filter-chip" onclick="closeExercisePreview()">Cancel</button>
      </div>
    </div>
  `;

  setTimeout(() => modalOverlay.classList.add('active'), 10);
}

function closeExercisePreview() {
  const modalOverlay = document.getElementById('exerciseModal');
  if (modalOverlay) {
    modalOverlay.classList.remove('active');
  }
}

window.openExercisePreview = openExercisePreview;
window.closeExercisePreview = closeExercisePreview;
