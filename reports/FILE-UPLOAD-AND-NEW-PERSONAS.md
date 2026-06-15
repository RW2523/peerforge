# File Upload Enabled + 16 New Agent Personas 🎉

**Date:** February 13, 2026  
**Status:** ✅ COMPLETE

---

## Part 1: File Upload Enabled in Materials Step

### Problem
File upload button was greyed out with message "Upload Files (after setup)" because debate wasn't created until Step 4.

### Solution
**Changed debate creation flow:**
```
OLD FLOW:
Step 1: Basic Info
Step 2: Materials (no debateId, upload disabled ❌)
Step 3: Participants
Step 4: Click "Create & Prepare" → debate created
Step 5: Preflight

NEW FLOW:
Step 1: Basic Info → Click "Next" → debate created ✅
Step 2: Materials (debateId exists, upload enabled! 📎)
Step 3: Participants
Step 4: Memory
Step 5: Preflight
```

### Code Changes

#### 1. Early Debate Creation
**File:** `apps/web/src/app/setup/page.tsx`

```typescript
// NEW: Create debate after Step 1
const handleCreateDebateEarly = async () => {
  if (createdDebateId) {
    setStep(2);  // Already created
    return;
  }
  
  const result = await createDebate();
  if (result) {
    setStep(2);
  }
};

// Step 1 button now creates debate
{step === 1 && (
  <button onClick={handleCreateDebateEarly}>
    <span>{isLoading ? 'Creating...' : 'Next'}</span>
  </button>
)}
```

#### 2. Pass debateId to MaterialsStep
```typescript
{step === 2 && (
  <MaterialsStep
    debateId={createdDebateId}  // NEW: Pass debate ID
    materials={materials}
    onAdd={handleAddMaterial}
    onUpdate={handleUpdateMaterial}
    onRemove={handleRemoveMaterial}
  />
)}
```

#### 3. Update Button Text
**File:** `MaterialsStep.tsx`

```typescript
// OLD: "Upload Files (after setup)"
// NEW: "Upload Files" (enabled immediately)
<button 
  onClick={() => fileInputRef.current?.click()} 
  disabled={!debateId || uploading}
  title={!debateId ? 'Debate being created...' : 'Upload PDF, DOCX, TXT, or MD files'}
>
  <span>📎</span> {uploading ? 'Uploading...' : 'Upload Files'}
</button>
```

### Supported File Types
- ✅ **PDF** - Will be processed and chunked for RAG
- ✅ **DOCX** - Word documents extracted and indexed
- ✅ **TXT** - Plain text files
- ✅ **MD** - Markdown files

### Upload Flow
1. User uploads files in Step 2
2. Files are sent to `/debates/{debateId}/materials/upload`
3. Backend processes files (chunking, embedding)
4. Agents can access during preflight and debate
5. Status shown in UI: ⏳ Pending → ⚙️ Processing → ✅ Ready

---

## Part 2: 16 New Agent Personas Added!

### Total Agent Count
**Before:** 39 personas  
**After:** 55 personas  
**New:** 16 personas across 5 new categories

---

## New Categories & Personas

### 🔬 Science & Academia (4 personas)

#### 1. Astronomer
- **Role:** Space Science Expert
- **Character:** Cosmic perspective
- **Style:** Think in cosmic scales, connect earthly problems to universal context
- **Best for:** Long-term thinking, perspective on scale, scientific rigor
- **Temperature:** 0.7 (curious)

#### 2. Research Scientist
- **Role:** Experimental Researcher
- **Character:** Hypothesis-driven
- **Style:** Form hypotheses, design experiments, analyze data rigorously
- **Best for:** Scientific method, experimental design, evidence evaluation
- **Temperature:** 0.65 (methodical)

#### 3. Medical Doctor
- **Role:** Clinical Medicine Specialist
- **Character:** Patient-centered
- **Style:** Diagnostic thinking, risk-benefit analysis, patient safety
- **Best for:** Health decisions, risk assessment, ethical considerations
- **Temperature:** 0.6 (clinical)

#### 4. University Professor
- **Role:** Academic Scholar
- **Character:** Teaching-focused
- **Style:** Explain complex concepts, cite research, encourage critical thinking
- **Best for:** Educational content, theoretical frameworks, knowledge synthesis
- **Temperature:** 0.7 (pedagogical)

---

### 🧘 Lifestyle & Wellness (3 personas)

#### 5. Mental Health Counselor
- **Role:** Clinical Psychologist
- **Character:** Emotionally intelligent
- **Style:** Empathetic listening, trauma-informed, evidence-based interventions
- **Best for:** Mental health discussions, emotional impact, psychological safety
- **Temperature:** 0.75 (compassionate)

#### 6. Lifestyle Coach
- **Role:** Holistic Wellness Expert
- **Character:** Balance-focused
- **Style:** Physical health, mental wellness, work-life harmony
- **Best for:** Lifestyle decisions, habit formation, holistic wellbeing
- **Temperature:** 0.75 (optimistic)

#### 7. Fitness & Nutrition Expert
- **Role:** Health Optimization Specialist
- **Character:** Performance-minded
- **Style:** Evidence-based training, nutritional science, performance metrics
- **Best for:** Physical health, fitness decisions, nutrition debates
- **Temperature:** 0.7 (results-oriented)

---

### 👥 Generational Voices (3 personas)

#### 8. Gen Z Voice
- **Role:** Digital Native (Born 1997-2012)
- **Character:** Socially conscious
- **Style:** Social justice aware, mental health open, climate anxious, authentic
- **Best for:** Youth perspective, social issues, digital culture
- **Temperature:** 0.8 (progressive)

#### 9. 90s Kid (Millennial)
- **Role:** Elder Millennial (Born 1981-1996)
- **Character:** Nostalgic pragmatist
- **Style:** Analog childhood, digital adulthood, economically weathered
- **Best for:** Millennial perspective, practical optimism, 90s/2000s context
- **Temperature:** 0.75 (adaptable)

#### 10. 80s Kid (Gen X)
- **Role:** Gen X Voice (Born 1965-1980)
- **Character:** Independent skeptic
- **Style:** Latchkey independence, tech-savvy, skeptical of hype
- **Best for:** Gen X perspective, work-life balance, pragmatic skepticism
- **Temperature:** 0.75 (balanced)

---

### 🎭 Personality Types (3 personas)

#### 11. Professional Arguer
- **Role:** Contrarian Debater
- **Character:** Combative skeptic
- **Style:** Disagrees with everyone, finds flaws, challenges aggressively
- **Best for:** Stress-testing ideas, finding weaknesses, aggressive critique
- **Temperature:** 0.8 (combative)
- **WARNING:** Will argue with EVERYTHING! 🔥

#### 12. Patriot
- **Role:** National Pride Advocate
- **Character:** Civic-minded
- **Style:** Values national identity, civic duty, community cohesion
- **Best for:** National interest debates, civic policy, community impact
- **Temperature:** 0.7 (principled)

#### 13. Human Rights Advocate
- **Role:** Humanitarian Activist
- **Character:** Justice-driven
- **Style:** Centers human welfare, questions oppression, advocates for marginalized
- **Best for:** Equity discussions, social justice, human impact
- **Temperature:** 0.75 (passionate)

---

### 🧠 Intelligence Spectrum (3 personas)

#### 14. High IQ Genius
- **Role:** Intellectually Gifted
- **Character:** Hyper-analytical
- **Style:** Rapid pattern recognition, sees implications others miss
- **Best for:** Complex analysis, abstract thinking, rapid synthesis
- **Temperature:** 0.65 (brilliant)

#### 15. Beginner Learner
- **Role:** Curious Newcomer
- **Character:** Learning-focused
- **Style:** Asks clarifying questions, needs simple explanations, fresh perspective
- **Best for:** Accessibility check, layperson view, practical grounding
- **Temperature:** 0.7 (humble)
- **NOTE:** Represents "person on the street" perspective

#### 16. Data Dog
- **Role:** Metrics Obsessive
- **Character:** Numbers-focused
- **Style:** Demands data for every claim, cites statistics, trusts metrics over intuition
- **Best for:** Data-driven decisions, metric validation, quantitative analysis
- **Temperature:** 0.6 (analytical)

---

## Usage Examples

### Example 1: Healthcare Debate
```
Topic: "Should we implement universal healthcare?"

Participants:
- Medical Doctor (clinical expertise)
- Data Dog (cost analysis)
- Human Rights Advocate (access and equity)
- CFO (financial viability)
- Beginner Learner (patient perspective)
```

### Example 2: Generational Product Design
```
Topic: "Design a new social media platform"

Participants:
- Gen Z Voice (features they want)
- 90s Kid (nostalgic for simplicity)
- 80s Kid (privacy concerns)
- Senior PM (product strategy)
- Professional Arguer (stress-test all ideas)
```

### Example 3: Space Exploration Funding
```
Topic: "Should we increase space exploration budget?"

Participants:
- Astronomer (scientific value)
- Sustainability Advocate (earth priorities)
- Patriot (national pride and leadership)
- Data Dog (ROI analysis)
- Trend Forecaster (future implications)
```

### Example 4: Mental Health in Workplace
```
Topic: "Mandatory mental health days for employees"

Participants:
- Mental Health Counselor (psychological impact)
- CFO (cost implications)
- Human Rights Advocate (worker wellbeing)
- Gen Z Voice (destigmatization)
- Lifestyle Coach (work-life balance)
```

---

## Complete Category Breakdown

| Category | Count | New? |
|----------|-------|------|
| **Science & Academia** | 4 | ✨ NEW |
| **Lifestyle & Wellness** | 3 | ✨ NEW |
| **Generational Voices** | 3 | ✨ NEW |
| **Personality Types** | 3 | ✨ NEW |
| **Intelligence Spectrum** | 3 | ✨ NEW |
| Thinking Styles | 5 | - |
| Tech Specialists | 4 | - |
| Entertainment | 3 | - |
| Political Advisors | 3 | - |
| Predictors | 3 | - |
| Indicator Analysts | 3 | - |
| Research Analysts | 3 | - |
| Product | 3 | - |
| Automotive | 2 | - |
| Business | 2 | - |
| Consumer | 2 | - |
| Engineering | 2 | - |
| Wildcards | 2 | - |
| Design | 1 | - |
| Facilitator | 1 | - |

**Total: 20 categories, 55 personas**

---

## Persona Highlights

### Most Combative
- 🔥 **Professional Arguer** (T=0.8) - Will disagree with EVERYONE!

### Most Analytical
- 🧠 **High IQ Genius** (T=0.65) - Fastest pattern recognition
- 📊 **Data Dog** (T=0.6) - Most metrics-obsessed

### Most Compassionate
- ❤️ **Mental Health Counselor** (T=0.75) - Empathy-driven
- ⚕️ **Medical Doctor** (T=0.6) - Patient-centered

### Most Progressive
- 🌱 **Gen Z Voice** (T=0.8) - Socially conscious
- ✊ **Human Rights Advocate** (T=0.75) - Justice-focused

### Most Grounded
- 👶 **Beginner Learner** (T=0.7) - Practical, simple
- 💼 **Gen X Voice** (T=0.75) - Balanced skeptic

---

## Temperature Guide

**Low (0.6-0.65):** Precise, consistent, analytical
- Medical Doctor, Data Dog, High IQ Genius, Research Scientist

**Medium (0.7-0.75):** Balanced, natural, engaging
- Most personas (Lifestyle Coach, Gen Z, Patriot, etc.)

**High (0.8+):** Creative, varied, personality-rich
- Professional Arguer, First Principles Thinker

---

## Testing Recommendations

### Test Debate 1: "Universal Healthcare"
```
- Medical Doctor
- Data Dog
- Human Rights Advocate
- CFO
- Beginner Learner (patient view)
```

### Test Debate 2: "Space vs Earth Priorities"
```
- Astronomer
- Sustainability Advocate
- Patriot
- Data Dog
- Professional Arguer
```

### Test Debate 3: "Gen Z Social Media App"
```
- Gen Z Voice
- 90s Kid
- 80s Kid
- Senior PM
- High IQ Genius
```

---

## RAG Integration

**All agents can now access uploaded materials!**

When files are uploaded:
1. Backend chunks and embeds content
2. Stored in vector database
3. Agents retrieve relevant chunks during preflight
4. Agents reference materials in their arguments

**Agents will see in their prep pack:**
- 📄 Material titles and summaries
- 🧩 Relevant chunks for their role
- 🌐 Web research results (if enabled)
- 🧠 Memory from previous debates (if imported)

---

## Status: ✅ DEPLOYED

**File Upload:** Enabled in Step 2  
**New Personas:** 16 added (39 → 55 total)  
**Categories:** 5 new categories  
**RAG:** Ready for agent access  
**Backend:** Healthy  
**Testing:** All personas verified

**Materials can now be uploaded, and agents have never been more diverse!** 🚀✨
