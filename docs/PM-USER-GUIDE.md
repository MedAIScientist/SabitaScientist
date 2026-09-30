# EvoScientist Project Management (PM) — User Guide

A full-stack research management platform for university labs. Manage projects,
experiments, publications, grants, lab members, and AI-assisted research tools
from a single dashboard.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Lab Management](#2-lab-management)
3. [Project Management](#3-project-management)
4. [Task & Kanban Board](#4-task--kanban-board)
5. [Experiments](#5-experiments)
6. [AI-Powered Research Tools](#6-ai-powered-research-tools)
7. [Publications Pipeline](#7-publications-pipeline)
8. [Domain-Specific Use Cases](#8-domain-specific-use-cases)
9. [Grants & Conferences](#9-grants--conferences)
10. [IRB / Ethics Approvals](#10-irb--ethics-approvals)
11. [Admissions Pipeline](#11-admissions-pipeline)
12. [Lab Wiki](#12-lab-wiki)
13. [Research Impact](#13-research-impact)
14. [MCP Servers & Memory](#14-mcp-servers--memory)
15. [Reports & Analytics](#15-reports--analytics)
16. [Settings & Administration](#16-settings--administration)

---

## 1. Getting Started

### Accessing the Platform

Open your browser and navigate to the PM dashboard URL provided by your
institution (e.g., `https://pm.evoscientist.university.edu`). The platform is
a single-page web application — once loaded, navigation happens instantly
without page reloads.

**System requirements:** Any modern browser (Chrome, Firefox, Safari, Edge).
No installation or plugins required. The platform works on desktop and tablet.

### Authentication

Two login methods are available:

**Password Login**
1. On the login screen, enter your **username** and **password** in the
   provided fields.
2. Click **SIGN IN**.
3. These credentials are provided by your lab PI or system administrator.
   If you do not have them, ask your PI to create an account for you.

**Sign in with Microsoft** (recommended)
1. If your institution uses Microsoft 365 (Entra ID), you will see a
   **"SIGN IN WITH MICROSOFT"** button below the login form.
2. Click this button — you will be redirected to your institution's
   Microsoft login page.
3. Enter your university email and password (or use single sign-on if
   already authenticated on your device).
4. After successful authentication, you are redirected back to the
   dashboard and automatically logged in.

> **Note:** The Microsoft option is only available if your institution has
> configured it. If you do not see the button, use password login instead.

### First Login — Setup Wizard

The very first time the platform is accessed (no admin user exists), a
**Setup Wizard** appears automatically:

1. **Create Admin Account**: Enter a username, password, and email for the
   initial system administrator.
2. Click **Create Admin**.
3. You are automatically logged in as the admin.
4. From here, you can create labs, add users, and configure the system.

If someone else has already completed the setup, you will see the standard
login screen instead.

### What You See After Login

Once logged in, the **Projects** page is your home. The top navigation bar
provides access to all sections:

| Nav Item | Who Can See It | Purpose |
|---|---|---|
| **Projects** | Everyone | Your project portfolio — create and manage research projects |
| **Labs** | Everyone | Lab management and membership |
| **Publications** | Everyone | Paper lifecycle — from draft to published |
| **Grants** | Everyone | Research funding and grant tracking |
| **Conferences** | Everyone | Conference deadlines and submissions |
| **IRB** | Everyone | Ethics approvals and protocol management |
| **Admissions** | PI, Admin | Graduate applicant pipeline |
| **Reports** | Everyone | Cross-project analytics and printable reports |
| **Admin** | Admin only | System-wide administration and user management |
| **Profile** | Everyone | Your account settings and theme preference |

### Basic Terminology

| Term | Meaning |
|---|---|
| **Lab** | A research group led by a PI, containing members and projects |
| **Project** | A research endeavor with tasks, experiments, and publications |
| **Task** | A discrete work item on a Kanban board |
| **Experiment** | A structured research activity with hypothesis, protocol, and entries |
| **Phase** | A stage in the research workflow (e.g., Data Collection) |
| **Entry** | A note, result, or file attached to an experiment |
| **Run** | An AI agent execution tied to a task |
| **Assist** | An AI writing assistant session tied to an experiment |

---

## 2. Lab Management

Labs are the organizational unit of the platform. Every project belongs to a
lab, and every user belongs to a lab as a member with a specific role.

### Why Use Labs?

Labs allow you to:
- Organize projects by research group
- Control access and permissions for members
- Track lab-wide research impact and citations
- Maintain a shared wiki for protocols and knowledge
- View PI-level analytics across all lab projects

### Creating a Lab

**Example scenario:** Dr. Ozge Şensoy is starting a new biomedical engineering
lab at her university. She needs to create the lab in the system.

1. Click **Labs** in the navigation bar.
2. Click the **+ New Lab** button (top-right).
3. Fill in the form:
   - **Lab Name**: `Şensoy Biomedical Engineering Lab`
   - **Department**: `Department of Biomedical Engineering`
   - **University**: `Istanbul Medipol University`
4. Click **Create**.

The lab is now created. Dr. Şensoy is automatically the first member and
assigned the **PI** role.

### Finding and Opening a Lab

The Labs page shows all labs in the system. Each card displays:
- Lab name, department, and university
- Member count
- Project count

Click a lab card to open its detail page.

### Managing Lab Members

**Example:** Dr. Şensoy needs to add her postdoc and two PhD students to
the lab.

1. Open the **Şensoy Biomedical Engineering Lab**.
2. Scroll to the **Members** section.
3. Click **Add Member**.
4. Search for a username (e.g., `mehmet.koç`).
5. Select a role from the dropdown:
   - **Postdoc** for Dr. Koç (can create/edit projects and experiments)
   - **PhD** for graduate students (can create/edit experiments)
6. Click **Add**.

The member now appears in the list with their role badge.

To **change a role**: Click the role dropdown next to a member and select
a new role. Changes take effect immediately.

To **remove a member**: Click the X/remove icon next to their name.

### Member Roles and Permissions

| Role | Can Create Projects | Can Create Experiments | Can Manage Members | Can View Analytics |
|---|---|---|---|---|
| **PI** | Yes | Yes | Yes | Yes |
| **Admin** | Yes | Yes | Yes | Yes |
| **Postdoc** | Yes | Yes | No | Yes |
| **PhD** | No | Yes | No | No |
| **MSc** | No | No (view only) | No | No |
| **Technician** | No | Yes | No | No |
| **Visitor** | No | No (view only) | No | No |

### Moving Between Labs

A user can be a member of multiple labs simultaneously. Each lab maintains
its own member list and roles. Switch between labs from the Labs page.

---

## 3. Project Management

Projects are the core unit of research organization. Each project contains
tasks (on a Kanban board), experiments, publications, and AI research tools.

### Creating a Project

**Example:** Dr. Şensoy is starting a project on "Single-cell RNA-seq Analysis
for Alzheimer's Disease Biomarkers."

1. Click **Projects** in the navigation bar.
2. Click **+ New Project**.
3. Fill in:
   - **Project Name**: `scRNA-seq Biomarkers in Alzheimer's Disease`
   - **Description** (optional):
     ```
     Analyzing single-cell transcriptomics data from Alzheimer's patient
     brain samples to identify novel cell-type-specific biomarkers.
     Collaborators: Istanbul Medical Faculty Neurology Department.
     ```
   - **Lab**: Select `Şensoy Biomedical Engineering Lab`
   - **Template**: Select **Life Science** (pre-populates phases like
     Literature Review, Sample Preparation, Data Collection, Analysis,
     Validation, Writing)
4. Click **Create**.

The project is created and you are taken to its Kanban board, pre-populated
with phases from the Life Science template.

### Using Templates

Templates save time by pre-configuring project phases and structure:

| Template | Pre-built Phases | Best For |
|---|---|---|
| **Life Science** | Lit Review, Sample Prep, Data Collection, Analysis, Validation, Writing | Wet-lab and bioinformatics research |
| **Medical Research** | Ethics Approval, Patient Recruitment, Data Collection, Analysis, Writing, Submission | Clinical studies and medical trials |
| **ML Research** | Literature Review, Data Preparation, Model Development, Training, Evaluation, Deployment, Paper Writing | Machine learning and AI research |

You can always add, remove, or rename phases after creation.

### The Project Dashboard

The Projects page lists all your projects. Each project card shows:

```
┌──────────────────────────────────────────────┐
│  scRNA-seq Biomarkers in Alzheimer's Disease  │
│  Şensoy Biomedical Engineering Lab            │
│                                               │
│  Tasks:  5 Planned / 3 In Progress / 2 Done   │
│  Experiments: 4                               │
│  Members: [A] [M] [Z]                        │
│                                               │
│  [Open Board]  [Report]  [⚙]                  │
└──────────────────────────────────────────────┘
```

- **Colored bars** show task status distribution at a glance
- **Member avatars** show who is working on this project
- Click anywhere on the card to enter the Kanban board

### Project Settings

On the Kanban board, click the **gear icon** (⚙) to open project settings:

- **Edit Name / Description**: Update project details.
- **Manage Members**: Add or remove project members (independent of lab
  membership — you can invite collaborators from other labs).
- **Archive Project**: Archives the project. It disappears from the main
  list but is not deleted. Contact an admin to un-archive.
- **Delete Project**: Permanently removes the project and all its data.
  Use with caution.

### Project Members vs Lab Members

A project can have members who are not in the project's lab. This is useful
for cross-lab collaborations. Project roles are:
- **Owner**: Full control (usually the PI or project lead)
- **Editor**: Can create and modify tasks, experiments, publications
- **Viewer**: Read-only access

To add a collaborator from another lab:
1. Open **Project Settings → Members**.
2. Click **Add Member**.
3. Search for the user's username.
4. Assign a role (Editor or Viewer).

---

## 4. Task & Kanban Board

The Kanban board is the main workspace for managing research tasks within a
project. It visualizes your workflow and helps track progress.

### Board Layout

A project's board is organized as a grid:

```
         ┌──────────┐  ┌──────────┐  ┌──────────┐
         │ PLANNED  │  │IN PROGRESS│  │ COMPLETE │
┌────────┼──────────┼──┼──────────┼──┼──────────┤
│Phase 1 │ ┌──┐     │  │ ┌──┐     │  │ ┌──┐     │
│Lit Rev │ │T1│     │  │ │T3│     │  │ │T2│     │
│        │ └──┘     │  │ └──┘     │  │ └──┘     │
├────────┼──────────┼──┼──────────┼──┼──────────┤
│Phase 2 │ ┌──┐     │  │          │  │          │
│Data    │ │T4│     │  │          │  │          │
│Collect │ └──┘     │  │          │  │          │
└────────┴──────────┴──┴──────────┴──┴──────────┘
```

- **Columns** represent status: **PLANNED** → **IN PROGRESS** → **COMPLETE**
- **Rows (swimlanes)** represent phases of the project
- **Cards** represent individual tasks
- Drag cards between columns to update status

### Creating a Task

**Example:** Dr. Şensoy needs to create a task for "Download and preprocess
scRNA-seq data from GEO database."

1. On the Kanban board, click the **+** button in the **PLANNED** column
   of the **Data Collection** phase.
2. Fill in the task form:
   - **Title**: `Download GEO datasets and run QC preprocessing`
   - **Description**:
     ```
     Download datasets GSE123456 and GSE789012 from GEO.
     Run standard QC pipeline: filter doublets, normalize,
     identify highly variable genes.
     Expected output: cleaned count matrices.
     ```
   - **Assignee**: Search for `mehmet.koç` and select
   - **Priority**: **High**
   - **Due Date**: `2026-08-15`
3. Click **Create**.

The task card appears in the PLANNED column of Data Collection phase.

### Moving Tasks (Drag and Drop)

- Drag a task from **PLANNED** to **IN PROGRESS** when work begins.
- Drag from **IN PROGRESS** to **COMPLETE** when finished.
- The system records who moved the task and when (visible in task history).

### Task Detail Panel

Click any task card to open the detail panel with four tabs:

**Details Tab:**
- View and edit title, description, assignee, priority, due date
- See creation date, last updated, and status history

**Notes Tab (LabNotesTab):**
- Add comments and lab notes to the task
- Each note shows author and timestamp
- Useful for recording decisions, meeting notes, or troubleshooting steps
- **Example:**
  ```
  Mehmet Koç — 2026-07-10 14:32
  GEO download completed. GSE123456 had 12 samples,
  GSE789012 had 8 samples. QC passed for all except
  2 samples in GSE789012 (high mitochondrial content).
  ```

**AI Runs Tab (AiRunsTab):**
- View all AI agent executions linked to this task
- Each run shows agent type, prompt, current status, and output
- Useful for tracking AI-assisted research activities

**Edit Tab (TaskEditForm):**
- Inline editing form for all task properties
- Changes are saved immediately

### Task Dependencies

Tasks can depend on each other. This enforces workflow ordering.

**Example:** "Data Analysis" depends on "Data Preprocessing" being complete.

1. Open the **Data Analysis** task detail panel.
2. Go to the **Dependencies** section.
3. Click **Add Dependency**.
4. Search for `Data Preprocessing` and select it.
5. Choose dependency type:
   - **Hard**: Data Analysis cannot start until Data Preprocessing is
     COMPLETE. The system blocks status changes.
   - **Soft**: Data Analysis should consider Data Preprocessing's outputs,
     but is not blocked.

**Visual indicator:** Tasks with hard dependencies show a lock icon in
their PLANNED column until the prerequisite is complete.

### Bulk Actions

Select multiple tasks using checkboxes, then perform bulk operations:

1. Check the boxes next to the tasks you want to modify.
2. A **Bulk Action Bar** appears at the bottom.
3. Choose an action:
   - **Set Status**: Move all selected to PLANNED / IN PROGRESS / COMPLETE
   - **Set Priority**: Apply Low / Medium / High / Critical to all
   - **Set Assignee**: Assign all to the same person
   - **Move Phase**: Move all to a different phase

**Use case:** After a lab meeting, you decide that 5 literature review
tasks should be moved from PLANNED to IN PROGRESS and assigned to a new
PhD student. Select all 5, set status to IN PROGRESS, assign the student
— done in two clicks.

### Phase Management

Phases represent stages of the research lifecycle. Each phase creates a
horizontal swimlane on the board.

**Adding a Phase:**
1. Click the **+** icon in the phase header area.
2. Enter the phase name (e.g., `Ethics Approval`).
3. The new swimlane appears at the bottom.

**Renaming a Phase:**
- Click the phase name to edit inline.
- Press Enter or click away to save.

**Reordering Phases:**
- Drag the phase header horizontally to reorder.
- All tasks move with the phase.

**Deleting a Phase:**
- Click the delete icon on the phase header.
- Tasks in the phase are unassigned (not deleted).
- Confirm the deletion in the dialog.

**Example phases for an ML Research project:**
1. Literature Review
2. Dataset Preparation
3. Model Development
4. Training & Tuning
5. Evaluation & Ablation
6. Paper Writing
7. Submission

---

## 5. Experiments

Experiments are the scientific core of the platform. Each experiment
captures a complete research activity with hypothesis, methodology, data,
and results.

### Creating an Experiment

**Example:** Dr. Şensoy's PhD student Zeynep is running a differential
expression analysis experiment.

1. From the project, click the **Experiments** tab (or navigate to
   `/projects/:id/experiments`).
2. Click **+ New Experiment**.
3. Fill in the form:

   | Field | Example Value |
   |---|---|
   | **Title** | `Differential Expression: Alzheimer's vs Control Microglia` |
   | **Hypothesis** | `Microglial cells in Alzheimer's patients show upregulation of inflammatory pathways (TNF-α, NF-κB) and downregulation of homeostatic markers (CX3CR1, P2RY12) compared to age-matched controls.` |
   | **Protocol** | `Using Seurat v5, normalize with SCTransform. Find conserved markers between AD and control microglia clusters. Use MAST for differential expression. Filter: |log2FC| > 0.25, adj. p < 0.05.` |
   | **Tags** | `rna-seq, microglia, alzheimers, differential-expression` |
   | **Deadline** | `2026-09-01` |
   | **Phase** | `Data Analysis` |

4. Click **Create**.

The experiment appears in the experiments list with its status (planned),
hypothesis preview, and linked phase.

### Experiment Detail View

Click an experiment to open its detail page, which shows:

- **Header:** Title, status, phase, tags, deadline
- **Hypothesis:** Full hypothesis text
- **Protocol:** Methodology description
- **Entries:** Chronological list of notes, results, and attachments
- **Linked Tasks:** Tasks connected to this experiment
- **Assists:** AI writing assistant sessions

### Experiment Entries

Entries are the building blocks of an experiment. There are three types:

**Notes** — For observations, ideas, and methodology notes:
```
┌──────────────────────────────────────────────┐
│  Note: Initial QC observations               │
│  2026-07-12 by Zeynep                        │
├──────────────────────────────────────────────┤
│  After filtering:                            │
│  - 10,234 cells remain (from 12,456)         │
│  - 2,000 highly variable genes identified    │
│  - PCA shows separation by condition         │
│  - UMAP clusters need parameter tuning       │
└──────────────────────────────────────────────┘
```

**Results** — For data, findings, and analysis output:
```
┌──────────────────────────────────────────────┐
│  Result: Differential Expression Results     │
│  2026-07-20 by Zeynep                        │
├──────────────────────────────────────────────┤
│  Top upregulated in AD microglia:            │
│  - TNF-α: log2FC = 1.82, p.adj = 2.3e-15    │
│  - IL1B: log2FC = 1.45, p.adj = 4.1e-12     │
│  - NFKB1: log2FC = 0.92, p.adj = 1.8e-08    │
│                                              │
│  Top downregulated in AD microglia:          │
│  - CX3CR1: log2FC = -1.34, p.adj = 3.2e-10  │
│  - P2RY12: log2FC = -1.12, p.adj = 5.6e-09  │
└──────────────────────────────────────────────┘
```

**Attachments** — Files, images, datasets:
- Upload figures (PNG, JPG, SVG)
- Upload data files (CSV, RDS, H5, NPZ)
- Upload PDFs (papers, protocols, forms)
- Files are stored in S3-compatible storage (Garage)
- Max upload size is configurable (default 50 MB)

To add an entry:
1. Open the experiment.
2. Click **Add Entry**.
3. Select type: **Note**, **Result**, or **Attachment**.
4. For text entries: write in Markdown (supports headings, lists, code
   blocks, tables, math via LaTeX).
5. For attachments: click to upload a file.
6. Click **Save**.

### Linking Tasks to Experiments

Connect experiments to tasks on the Kanban board:

1. Open the experiment.
2. Click **Link Task**.
3. A dialog shows the project's task list.
4. Select one or more tasks (e.g., `Run differential expression analysis`).
5. Click **Link**.

The link is bidirectional:
- The experiment page shows the linked task.
- The task detail panel shows the linked experiment.
- Changing the experiment's phase can automatically update related tasks.

### Experiment Status Lifecycle

Experiments move through statuses:
1. **Planned** — Created, hypothesis defined, not yet started
2. **In Progress** — Active work, entries being added
3. **Complete** — All entries finalized, results obtained
4. **Abandoned** — No longer pursued (hypothesis rejected or deprioritized)

Status can be changed from the experiment detail page.

### AI Writing Assistant

The AI assistant helps you write about your experiment:

1. Click **AI Assist** on the experiment page.
2. The AI reads your experiment's hypothesis, protocol, and entries.
3. Choose what to generate:
   - **Draft Methods Section**: Converts your protocol into paper-ready
     methods prose.
   - **Summarize Results**: Generates a concise results summary with key
     numbers.
   - **Write Discussion Points**: Suggests interpretations of your findings.
   - **Generate Figure Description**: Describes what a figure should show.
4. Click **Generate**.
5. Output streams in real-time (token by token, like ChatGPT).
6. Review the output and click **Save as Entry** to add it as a Note or
   Result entry.

**Example AI Assist output for "Summarize Results":**
```
Differential expression analysis of scRNA-seq data comparing Alzheimer's
disease (AD) versus control microglia revealed 847 significantly
differentially expressed genes (|log2FC| > 0.25, adj. p < 0.05). Among
these, 512 were upregulated and 335 were downregulated in AD microglia.

Key findings:
1. Inflammatory pathway activation: TNF-α (log2FC = 1.82), IL1B (log2FC
   = 1.45), and NFKB1 (log2FC = 0.92) were among the most strongly
   upregulated genes, confirming neuroinflammatory activation.
2. Homeostatic marker loss: CX3CR1 (log2FC = -1.34) and P2RY12
   (log2FC = -1.12) were significantly downregulated, indicating loss
   of microglial homeostatic function in AD.
3. These results are consistent with published findings in [citation]
   and extend them by identifying cell-type-specific signatures at
   single-cell resolution.
```

---

## 6. AI-Powered Research Tools

The platform integrates AI via Groq (Mixtral 8x7B model) for a variety of
research tasks. These tools are accessible from the **Research Tools** panel
on the project Kanban board, and from the project's AI tools menu.

### How AI Tools Work

All AI tools follow the same pattern:
1. You provide context (project description, experimental data, or a prompt)
2. The AI processes your input and generates structured output
3. Results can be saved as experiment entries or exported as text
4. Streaming output lets you see results as they are generated

### Hypothesis Generation

**When to use:** You have a project idea but need structured, testable
hypotheses to guide your experiments.

**Example:**
1. Navigate to **Research Tools → Generate Hypothesis**.
2. Topic: `Single-cell transcriptomic signatures of microglial
   senescence in Alzheimer's disease`
3. The AI generates 3–5 hypotheses like:

   ```
   Hypothesis 1: Senescent microglia in AD exhibit a distinct
   transcriptional signature characterized by upregulation of
   p16INK4a (CDKN2A), p21 (CDKN1A), and senescence-associated
   secretory phenotype (SASP) factors including IL-6 and MMP3,
   which can be identified through scRNA-seq clustering.

   Hypothesis 2: The proportion of senescent microglia correlates
   positively with tau pathology burden (Braak stage) and
   negatively with cognitive scores (MMSE) in AD patients.

   Hypothesis 3: Pharmacological clearance of senescent microglia
   using senolytics (dasatinib + quercetin) rescues homeostatic
   microglial gene expression and reduces neuroinflammation in
   an AD mouse model.
   ```

4. Each hypothesis includes suggested experimental approaches and
   predicted outcomes.

### Research Ideation

**When to use:** You want to explore novel research directions or find
gaps in the current literature.

**Example:**
1. Navigate to **Research Tools → Research Ideation**.
2. Focus area: `Microglia-astrocyte crosstalk in neurodegeneration`
3. The AI produces structured ideas:

   ```
   Idea 1: Ligand-Receptor Analysis of Glial Communication
   - Use CellChat or NicheNet on public AD scRNA-seq datasets
   - Identify perturbed signaling pathways between microglia and
     astrocytes
   - Validate top candidates using co-culture experiments

   Idea 2: Spatial Transcriptomics of Glial Interactions
   - Apply MERFISH or Visium HD to AD brain sections
   - Map microglia-astrocyte proximity and ligand expression
   - Correlate spatial interaction patterns with pathology
   ```

### Methodology Validation

**When to use:** You have a proposed experimental design and want an
AI review of its strengths, weaknesses, and potential issues.

**Example:**
1. Navigate to **Research Tools → Validate Methodology**.
2. Proposed methods:
   ```
   We will use 10x Genomics scRNA-seq on post-mortem human brain
   tissue from 10 AD patients and 10 controls. Libraries will be
   sequenced on NovaSeq 6000. Analysis will use Seurat for
   clustering and MAST for differential expression.
   ```
3. The AI reviews and returns:

   ```
   Strengths:
   - 10x Genomics is well-suited for large-scale single-cell profiling
   - MAST is appropriate for differential expression in scRNA-seq
   - Balanced sample size (10 vs 10) is reasonable for pilot studies

   Potential Issues:
   - Post-mortem interval (PMI) varies between samples — include PMI
     as a covariate in the model
   - Batch effects between sequencing runs — plan for Harmony or
     scVI integration
   - Sex and age matching should be verified between groups
   - Consider including a technical replicate or pooling strategy

   Recommendations:
   1. Add a tissue quality metric (RIN score) as a filtering criterion
   2. Plan for doublet detection (DoubletFinder or scrublet)
   3. Include at least one validation method (immunofluorescence or
      RNAscope) for top markers
   ```

### Literature Review (Automated)

**When to use:** You need a structured overview of a research area to
inform your project or paper introduction.

**Example:**
1. Navigate to **Research Tools → Literature Review**.
2. The AI searches web sources and synthesizes findings into a structured
   Markdown report:

   ```
   # Literature Review: Microglial Senescence in Alzheimer's Disease

   ## Background
   Microglial senescence has emerged as a key contributor to
   Alzheimer's disease pathology...

   ## Key Findings
   1. Senescent microglia accumulate with age and are found at higher
      densities in AD brains (Smith et al., 2023)
   2. These cells exhibit a distinct transcriptional program...

   ## Research Gaps
   - Limited single-cell resolution of senescent microglial states
   - Lack of validated surface markers for flow cytometry sorting

   ## Relevance to Your Project
   Your scRNA-seq approach is well-positioned to address Gap #1...
   ```

The review is automatically saved as an experiment entry in the project.

### Citation Verification

**When to use:** You have a list of citations and need to check if they
are accurate (not AI-hallucinated).

**Example:**
1. Navigate to **Research Tools → Verify Citations**.
2. Paste your citation list:
   ```
   Smith J, et al. (2023) Microglial senescence in Alzheimer's
   disease. Nature Neuroscience. 26:45-58.

   Chen L, et al. (2022) Single-cell atlas of human microglia.
   Cell. 185:100-120.
   ```
3. The AI checks each reference:

   ```
   ✓ Smith et al. 2023 — Verified. Published in Nature
     Neuroscience, 26:45-58. Found on PubMed (PMID: 36510045).

   ✗ Chen et al. 2022 — NOT VERIFIED. No record found in
     PubMed matching this title and journal. The volume/page
     range may be incorrect.
   ```

### Grant Proposal Writer

**When to use:** You need a draft grant proposal for a funding application.

**Example:** Dr. Şensoy is applying for a TÜBİTAK 1001 grant on her
microglial senescence project.

1. Navigate to **Research Tools → Grant Proposal**.
2. Select grant type: **TÜBİTAK 1001**
3. The AI generates a complete proposal:

   ```
   # Project Title
   Single-Cell Transcriptomic Characterization of Senescent Microglia
   in Alzheimer's Disease: Novel Biomarkers and Therapeutic Targets

   # Özet (Türkçe)
   Alzheimer hastalığında mikroglial senesansın tek hücre
   seviyesinde karakterizasyonu...

   # Abstract (English)
   Alzheimer's disease (AD) is the most common neurodegenerative
   disorder...

   # Amaç ve Hedefler
   Aim 1: Identify senescent microglia subtypes in AD...
   Aim 2: Validate top candidates using spatial transcriptomics...
   Aim 3: Test senolytic intervention in an AD mouse model...

   # Özgün Değer
   This project is the first to characterize microglial senescence
   at single-cell resolution in human AD tissue...

   # Yöntem
   1.1 Sample collection and scRNA-seq library preparation...
   1.2 Computational pipeline for senescence signature detection...

   # Bütçe
   - Personnel: 1 PhD student (36 months)...
   - Equipment: Sequencing reagents...
   - Travel: International conference presentations...
   ```

For Turkish agency grants (TÜBİTAK, TÜSEB), the proposal automatically
includes a Turkish abstract and follows the agency's required format.

### Auto Figure Generator

**When to use:** You have experimental results and want AI-generated
analysis code and figure descriptions.

1. Navigate to an experiment → **Generate Figures**.
2. The AI analyzes experiment data and produces:

   **Statistical Summary:**
   ```
   Differential expression analysis identified 847 DEGs
   (512 up, 335 down) between AD and control microglia.
   Top pathways: TNF signaling (p=1.2e-10), NF-kB (p=3.4e-8),
   Chemokine signaling (p=2.1e-6).
   ```

   **Python Code (matplotlib/seaborn):**
   ```python
   import matplotlib.pyplot as plt
   import seaborn as sns

   fig, axes = plt.subplots(1, 2, figsize=(12, 5))

   # Volcano plot
   sns.scatterplot(data=deg_results, x='log2FC', y='neg_log10_padj',
                   hue='regulation', ax=axes[0])
   axes[0].set_title('Volcano Plot: AD vs Control Microglia')

   # Heatmap of top markers
   sns.heatmap(top_markers, cmap='RdBu_r', center=0, ax=axes[1])
   axes[1].set_title('Top 20 Differentially Expressed Genes')
   ```

   **Figure Description:**
   ```
   Figure 1: Transcriptional changes in AD microglia.
   (A) Volcano plot showing differentially expressed genes...
   (B) Heatmap of top 20 DEGs across AD and control samples...
   ```

### AI Grant Writer

For detailed grant applications, the system produces agency-specific
proposals via the publication pipeline. The same TÜBİTAK 1001, NIH R01,
NSF, ERC, and Wellcome templates are available with proper formatting,
section headers, and page limits.

---

## 7. Publications Pipeline

The publication module manages the complete paper lifecycle — from initial
draft through submission, review, revision, and publication.

### Creating a Publication

**Example:** Dr. Şensoy is preparing a paper on her microglial senescence
findings for *Nature Neuroscience*.

1. Navigate to **Publications** → **+ New Publication**.
2. Fill in:

   | Field | Example Value |
   |---|---|
   | **Title** | `Single-cell transcriptomic profiling reveals senescent microglial subtypes in Alzheimer's disease` |
   | **Venue** | `Nature Neuroscience` |
   | **Venue Type** | `Journal` |
   | **Project** | `scRNA-seq Biomarkers in Alzheimer's Disease` |
   | **Abstract** | (leave blank for now — AI can draft it) |

3. Click **Create**.

The publication appears with status **Draft**.

### Publication Detail Page

Click a publication to open its detail page, which shows:

**Header Section:**
- Title, venue, current status badge
- Quick-action buttons: Draft Section, Revise, Respond to Reviewers,
  Generate AI Review, Submit

**Metadata Panel:**
- Title (editable)
- Venue and venue type
- Authors (comma-separated list)
- DOI and URL (for published papers)
- Abstract (full text, editable)

**Status Timeline:**
```
Draft ──→ Submitted ──→ Reviewing ──→ Accepted ──→ Published
                                    └──→ Rejected
```
- Click **Submit** to change status from Draft to Submitted
- Click **Accept** or **Reject** during review

**Linked Experiments:**
- Connect experiments whose data supports this publication
- Each link can specify which paper section uses that experiment
- During AI drafting, linked experiments provide context

**Pipeline Overview:**
- Visual timeline showing each stage of the publication process
- Version history with dates and notes

### AI Section Drafting

Draft each section of your paper using AI. The AI uses your project context,
linked experiments, and research data to generate text.

**Example: Drafting the Introduction:**
1. Open the publication, click **Draft Section**.
2. Select section: **Introduction**.
3. Choose writing style:
   - **Standard** — Balanced academic tone
   - **Concise** — Brief, to the point
   - **Detailed** — Comprehensive, longer form
4. Click **Generate**.
5. The AI produces:

   ```
   Alzheimer's disease (AD) is the most common cause of dementia,
   affecting approximately 55 million people worldwide [1].
   Neuroinflammation mediated by microglia has emerged as a key
   contributor to AD pathogenesis [2, 3]. Recent studies have
   demonstrated that microglia undergo senescence — a state of
   irreversible cell cycle arrest with a pro-inflammatory secretory
   phenotype — in the aging and AD brain [4, 5].

   However, the heterogeneity of senescent microglial states and
   their specific transcriptional signatures at single-cell
   resolution remain poorly characterized. Here, we performed
   single-cell RNA sequencing of post-mortem human brain tissue
   from AD patients and age-matched controls to identify and
   characterize senescent microglial subtypes...

   [Generated 3 citations from project context]
   ```

6. Review the output. Edit as needed. Click **Save** to store it
   (saved as a new version).

**Available sections:**

| Section | What the AI generates |
|---|---|
| **Abstract** | 150-250 word structured summary |
| **Introduction** | Background, gap, contribution, paper outline |
| **Methods** | Detailed methodology from experiment protocols |
| **Results** | Key findings with data references |
| **Discussion** | Interpretation, limitations, future work |
| **Conclusion** | Summary and broader impact |

### Drafting from an Experiment

Convert experiment data directly into a paper section:

1. Navigate to the experiment (e.g., `Differential Expression:
   Alzheimer's vs Control Microglia`).
2. Click **Draft to Publication**.
3. Select target:
   - **Target Publication**: `Single-cell transcriptomic profiling...`
   - **Target Section**: `Results`
4. The AI generates a results section incorporating the experiment's
   data, statistics, and figures.

### Revision

Request AI revision of any section:

1. Open the publication, click **Revise**.
2. Select the section to revise.
3. Enter instructions:
   ```
   Make the introduction more concise. Reduce to 3 paragraphs.
   Strengthen the gap statement in paragraph 2. Add a sentence
   about clinical significance at the end.
   ```
4. Optionally provide the specific text to revise (or the AI uses
   the current draft).
5. The AI generates a revised version.

### Reviewer Response

Generate responses to reviewer comments:

1. Open the publication, click **Respond to Reviewers**.
2. Paste the reviewer comments:
   ```
   Reviewer 1: The authors should provide validation of their
   top markers using an orthogonal method such as
   immunohistochemistry or RNAscope. The sample size is
   relatively small (n=10 per group).

   Reviewer 2: The discussion of microglial subtypes would
   benefit from comparison with the recent cell atlas published
   by Smith et al. (2023).
   ```
3. The AI generates professional responses:

   ```
   Response to Reviewer 1:
   We thank the reviewer for this important suggestion. We have
   now validated our top three markers (p16INK4a, CX3CR1, TNF-α)
   using RNAscope on adjacent tissue sections from the same
   samples. Results confirm the RNA-seq findings (see new
   Supplementary Figure 2) and are described in the revised
   Results section (page 8, lines 245-260).

   Regarding sample size: while we acknowledge that n=10 per
   group is modest, power analysis based on effect sizes from
   our pilot data indicates 80% power to detect log2FC > 0.5
   at α = 0.05. We have added this power analysis to the
   Methods section (page 5, lines 120-125).

   Response to Reviewer 2:
   We thank the reviewer for pointing us to this important
   reference. We have now incorporated a comparison with
   the Smith et al. (2023) microglial subtypes in the
   Discussion section (page 12, lines 310-325).
   ```

### AI Peer Review

Generate an AI review before submission for quality checking:

1. Open the publication, click **Generate AI Review**.
2. The AI analyzes the full publication and produces a structured review:

   ```
   ## AI Peer Review

   ### Summary
   This manuscript presents a single-cell transcriptomic analysis
   of senescent microglia in Alzheimer's disease. The work is
   timely and addresses an important gap in the field.

   ### Strengths
   1. Well-designed computational pipeline with appropriate
      quality control measures
   2. Clear presentation of differential expression results
      with statistical rigor
   3. Novel identification of distinct senescent subtypes

   ### Weaknesses
   1. The validation section could be strengthened with
      orthogonal methods
   2. Lack of discussion about potential batch effects
   3. Sample size justification would benefit from power analysis

   ### Specific Suggestions
   - Line 145: Consider adding UMAP visualization stratified by
     PMI to rule out batch effects
   - Line 234: The p-value threshold should be justified
   - Figure 3: Add confidence intervals to bar plots

   ### Overall Assessment
   Recommend: Minor Revision
   Score: 7/10
   ```

Use the AI review as a pre-submission checklist. Address the identified
issues before submitting to a real journal.

### Version Management

Each time you make significant changes, create a version:

1. On the publication detail page, click **New Version**.
2. Add version notes:
   ```
   Version 2: Incorporated reviewer responses. Added RNAscope
   validation data. Revised introduction for clarity.
   ```
3. Previous versions remain accessible in the **Versions** tab.
4. You can view or restore any previous version.

### Publication Status Workflow

```
Draft → Submitted → Reviewing → Accepted → Published
                      ↓
                   Rejected
```

- **Draft**: Working on the manuscript. AI drafting, revision available.
- **Submitted**: Sent to journal. Click "Submit" to mark.
- **Reviewing**: Under peer review.
- **Accepted**: Accepted for publication.
- **Published**: Final published version (add DOI and URL).
- **Rejected": Not accepted (can submit to another venue).

### Linking Experiments to Publications

Connect experiments that support your paper:

1. Open the publication, click **Link Experiment**.
2. Select an experiment from your project.
3. Optionally specify which section it supports (e.g., "Results",
   "Figure 2", "Supplementary Table 1").
4. During AI drafting, linked experiments provide rich context,
   including hypothesis, protocol, results, and figure descriptions.

### Full Paper Draft

Generate an entire paper draft from project context:

1. Navigate to **Research Tools → Draft Paper**.
2. The AI reads all project data (description, experiments, tasks) and
   generates a complete manuscript with abstract, introduction, methods,
   results, discussion, and conclusion.
3. Review and edit each section individually.

---

## 8. Domain-Specific Use Cases

The platform adapts to different research domains through flexible project
templates, customizable experiment types, and AI tools that understand
domain-specific language. Below are detailed walkthroughs for four fields.

### Clinical Studies

Clinical research involves patient recruitment, ethics approval, trial
registration, data collection, and regulatory compliance. The platform's
**Medical Research** template pre-configures appropriate phases.

**Example: Randomized Controlled Trial for a New Hypertension Drug**

*PI: Dr. Hasan Yılmaz, Cardiology Department*

**Project Setup:**
1. Click **+ New Project** → Select **Medical Research** template.
2. Name: `Phase II RCT: AHT-200 in Resistant Hypertension`
3. Template pre-creates phases:
   - Ethics Approval
   - Patient Recruitment
   - Baseline Assessment
   - Intervention & Follow-up
   - Data Analysis
   - Manuscript Writing
   - Regulatory Submission

**Phases in Action:**

**Phase: Ethics Approval**
- Create task: `Submit ethics application to IRB`
  - Priority: Critical | Due: before any patient contact
- Create task: `Register trial on ClinicalTrials.gov`
  - Assignee: Dr. Yılmaz | Due: same timeline as IRB
- Link IRB record: Navigate to **IRB** → Create protocol with
  institution name and protocol number → Link to project
- Use **AI Assist** on the Ethics Approval task:
  - Prompt: "Draft an informed consent form for a Phase II
    hypertension drug trial including risks, benefits,
    and withdrawal procedures."
  - The AI generates a consent form draft following ICH-GCP
    guidelines.

**Phase: Patient Recruitment**
- Create tasks for each recruitment site:
  - `Screen patients at Istanbul Medical Faculty`
  - `Screen patients at Ankara Cardiology Institute`
- Create experiment: `Baseline Patient Demographics`
  - In the experiment, create entries for each patient cohort
    with inclusion/exclusion criteria tracking
- Use **Research Tools → Generate Hypothesis**:
  - Topic: "Predictors of treatment response in resistant
    hypertension based on baseline renin levels"
  - The AI generates testable sub-hypotheses for exploratory
    analysis.

**Phase: Intervention & Follow-up**
- Create task: `Week 0: Randomization and drug administration`
- Create task: `Week 4: Interim analysis`
- Create task: `Week 12: Primary endpoint assessment`
- Use **Experiments** to track each follow-up visit:
  ```
  Experiment: 4-Week Follow-up — AHT-200 Group
  Hypothesis: AHT-200 reduces 24-hour ambulatory SBP by
  ≥10 mmHg compared to placebo at 4 weeks.
  Protocol: Double-blind, placebo-controlled. Primary endpoint:
  change in 24-hour ambulatory SBP. Secondary: adverse events,
  heart rate, laboratory values.
  ```
- Each follow-up window gets result entries with actual BP
  measurements, lab values, and adverse event logs.

**Phase: Data Analysis**
- Use **AI Assist** on the experiment:
  - "Summarize primary endpoint results: mean SBP change,
    confidence intervals, effect size."
  - The AI produces a structured summary ready for the
    manuscript Results section.
- Use **Research Tools → Validate Methodology**:
  - Describe: "We used a mixed-effects model for repeated
    measures (MMRM) with treatment, visit, and treatment-by-visit
    as fixed effects."
  - The AI checks for missing covariates, appropriate
    covariance structure, and handling of missing data.

**Phase: Manuscript Writing**
- Create a **Publication** titled:
  `Efficacy and Safety of AHT-200 in Resistant Hypertension:
  A Phase II Randomized Controlled Trial`
- Use **AI Draft → Methods** to generate the clinical methods
  section from the experiment protocols.
- Use **AI Draft → Results** with the linked experiments to
  generate a results section with proper CONSORT-style reporting.

---

#### EHR & PACS Data Integration — Privacy & Sandbox Constraints

University hospital systems provide two critical data sources that can
be processed inside secure sandboxes for research:

**EHR (Electronic Health Records):** Patient demographics, diagnoses,
medications, lab results, vital signs, and clinical notes.

**PACS (Picture Archiving and Communication System):** Medical images
(DICOM format): CT, MRI, X-ray, ultrasound, and PET scans.

**Critical Rules for Patient Data:**

| Rule | Enforcement |
|---|---|
| **De-identification before any processing** | Automated PHI removal pipeline runs at ingestion. No raw PHI enters the sandbox. |
| **No data download** | Patient-derived data never leaves the sandbox. Only aggregate results, model weights (trained on de-identified data), and figure PNGs can be exported. |
| **Sandbox-only processing** | All patient data processing happens inside isolated sandbox environments. The sandbox has no network egress to unauthorized destinations. |
| **Audit trail** | Every data access, transformation, and export is logged to the project's audit log. |
| **IRB-linked expiry** | Sandbox access auto-revokes when the linked IRB protocol expires. |

**Example: Deep Learning for Diabetic Retinopathy Screening**

*PI: Dr. Mehmet Yıldız, Department of Ophthalmology*

**Data Access Workflow:**

0. **Provision Research Sandbox:**
   - Create task: `Request sandbox environment from IT`
     - Description: "Provision isolated sandbox with access
       to de-identified EHR/PACS mirror. Sandbox spec:
       8 vCPU, 64 GB RAM, 1 TB NVMe, 1x A5000 GPU.
       Network: no internet egress. Allowed destinations:
       only git server and package registry mirror."
   - Create task: `Verify sandbox isolation`
     - Entry: **Note** — "Sandbox verified: no SSH access
       outside cluster, no S3 bucket sync, all package
       installs proxied through internal mirror.
       Audit logging enabled."
   - Link the sandbox verification as an experiment entry
     for compliance records.

1. **Data Governance & Compliance:**
   - Create task: `Obtain IRB approval for retrospective
     EHR/PACS analysis`
   - Create task: `Sign data usage agreement with Hospital
     IT and Patient Privacy Office`
   - Create task: `Register sandbox with Data Privacy Office`
   - Link the **IRB** record to the project — sandbox access
     will auto-expire when IRB expires.
   - Entry: **Note — De-identification Policy** —
     "All PHI must be removed BEFORE ingestion into the
     sandbox. The de-identification pipeline runs at the
     hospital data firewall. Only de-identified data crosses
     into the research sandbox. No PHI ever stored in the
     sandbox persistent storage. De-identification verified
     by Data Privacy Office."
   - Entry: **Note — No-Download Policy** —
     "Patient-derived data (images, tables, features,
     embeddings) cannot be downloaded from the platform.
     Only aggregate results (model weights, accuracy
     metrics, figure PNGs, cohort statistics without
     cell-level detail) may be exported. Any export is
     logged in the audit trail and requires PI approval."

2. **De-identified Data Ingestion:**
   - Create experiment: `EHR Ingestion — Diabetic Patients`
     ```
     Protocol (runs at hospital firewall, before sandbox):
     1. Query hospital data warehouse via HL7 FHIR API
     2. Inclusion: ICD-10 E11.xx, age ≥ 18, retinal exam 2020-2026
     3. De-identify: remove name, ID, exact DOB (keep year+month),
        phone, address. Replace patient ID with study hash.
     4. Only de-identified CSV crosses into research sandbox.
     Fields: study_id_hash, HbA1c, BP, creatinine, medications,
     comorbidities (binary), year_of_birth, gender.
     ```
     - Entry: **Result** — "12,847 patients. De-identified.
       Data dictionary: 24 columns, all PHI fields removed.
       SHA-256 hash used for patient linking across tables."
     - Data dictionary attached (column names + types only,
       no patient values).

   - Create task: `Set up de-identified PACS mirror`
     ```
     Description: Hospital PACS team runs DICOM de-identification
     at the firewall. Burned-in text removed via OCR masking.
     DICOM tags (PatientName, PatientID, etc.) cleared.
     Only de-identified DICOM forwarded to sandbox storage.
     Sandbox receives: `/data/retina_pacs/deid/`.
     ```
     - Entry: **Note** — "PACS mirror configured. 23,456 studies
       (1.2 TB) de-identified at firewall. Only de-identified
       DICOM files present in sandbox. Verification: random
       100-image sample checked for residual PHI — 0 found."

3. **Data Annotation with CVAT (in sandbox):**
   - CVAT runs inside the sandbox. Annotators access it
     through an internal URL. No data ever leaves the sandbox.
   - Create task: `Set up CVAT project for retinal image annotation`
     ```
     Description: Import 8,234 de-identified fundus images
     into CVAT inside sandbox. Labels: normal, mild NPDR,
     moderate NPDR, severe NPDR, PDR, DME. Assign to 3
     ophthalmology residents (sandbox user accounts).
     ```
   - Create experiment: `Annotation Quality Control`
     ```
     Protocol: 10% double-annotated. Cohen's kappa.
     Weekly consensus meetings. All annotation data
     stays inside sandbox.
     ```
     - Entry: **Result** — "Phase 1: 3,200 images annotated.
       Kappa = 0.78. 142 disagreements resolved.
       CVAT task export (COCO JSON) stored in sandbox:
       `/data/annotations/phase1_coco.json`."
     - Only the COCO JSON is referenced — no raw image
       download is possible. Annotations are tied to
       de-identified image hashes, not patient IDs.

4. **AI Model Development (in sandbox):**
   - All training runs execute inside the sandbox. Model
     weights are stored in sandbox storage. Only the trained
     model file (which contains no patient data) can be
     exported for deployment.
   - Create experiment: `RetinaNet for DR Severity Classification`
     ```
     Hypothesis: EfficientNet-B4 on de-identified fundus
     images achieves AUC ≥ 0.95 for referable DR.
     Protocol: 80/10/10 split. ImageNet weights.
     Augmentation: rotation, flip, color jitter.
     All processing inside sandbox.
     ```
     - Entry: **Result** — "Test set AUC: 0.967.
       Sensitivity: 0.94, Specificity: 0.91.
       Model weights exported (no patient data contained).
       Confusion matrix saved as figure PNG."
     - Model weights exported (approved export — no PHI).
     - Confusion matrix figure exported (aggregate only).

5. **EHR+PACS Combined Analysis (in sandbox):**
   - Create experiment: `Risk Factors for DR Progression`
     ```
     Protocol: Cox proportional hazards inside sandbox.
     All patient-level data stays in sandbox. Only
     coefficient tables and model diagnostics computed.
     ```
     - Entry: **Result** — "Hazard ratios: HbA1c > 8%: 2.34
       (95% CI: 1.89-2.91). C-statistic: 0.79.
       Kaplan-Meier curve exported as de-identified figure PNG."
     - KM curve exported as PNG (no patient-level data
      in the image — only aggregate survival curves).
   - Use **AI Assist** (sandboxed AI endpoint or local model):
     "Generate a Results section describing the Cox
     regression findings from the exported coefficient table."

**Export Approval Workflow:**
```
Export Request → PI Review → Data Privacy Office Approval → Export Logged → File Released
```

Only the following may be exported from the sandbox:
- **Model weights** (trained on de-identified data, no PHI)
- **Aggregate figures** (ROC curves, confusion matrices,
  Bland-Altman plots — no individual patient identifiable)
- **Coefficient tables** (hazard ratios, p-values — no raw data)
- **Annotation statistics** (counts, agreement scores — no images)

The following may **NEVER** be exported:
- Raw DICOM or NIfTI files
- Patient-level CSV or tables
- CVAT image exports (only annotation JSON, not the images)
- Any file containing PHI or quasi-identifiers

**Key integrations for EHR/PACS:**
- **IRB module** tracks ethics approval — sandbox access
  expires with the IRB
- **Audit log** records all sandbox access and export requests
- **Sandbox environment** is treated as an experiment resource —
  its provisioning, verification, and teardown are tracked
  as project tasks
- **De-identification pipeline** is a documented experiment
  protocol with version control
- **AI Assist** runs on de-identified data only (or uses a
  sandboxed local model for patient-near computation)

---

**Key integrations for clinical studies:**
- **IRB module** tracks ethics approval dates and expiry
- **Publications** can link to ClinicalTrials.gov identifier
- **Experiments** can record adverse events as structured entries
- **AI drafts** follow CONSORT reporting guidelines

---

### Wet Lab Studies

Wet lab research involves sample preparation, experimental protocols,
data collection from lab instruments, and iterative optimization.
The **Life Science** template is the starting point.

**Example: CRISPR Knockout Screen for Cancer Drug Targets**

*PI: Prof. Maria Santos, Molecular Biology Lab*

**Project Setup:**
1. Click **+ New Project** → Select **Life Science** template.
2. Name: `Genome-wide CRISPR Screen for AML Drug Targets`
3. Add custom phases if needed:
   - gRNA Library Design
   - Cell Culture & Transduction
   - Selection & Genomic DNA Extraction
   - NGS Library Prep & Sequencing
   - Data Analysis & Hit Identification
   - Validation
   - Paper Writing

**Phases in Action:**

**Phase: gRNA Library Design**
- Create task: `Design GeCKO v2 library targeting 19,000 genes`
  - Description: "Use Broad Institute's GPP portal. 4 gRNAs
    per gene, 1000 control gRNAs. Order from Addgene."
  - Assignee: Postdoc | Priority: High
- Create experiment: `gRNA Library Validation`
  - Entry type: **Note** — "Library amplified in STBL3
    competent cells. Transformation efficiency: 1.2e6 CFU/μg.
    Sequencing confirmed 98% coverage at 200x depth."
- Attach the sequencing QC report as an **Attachment** entry.

**Phase: Cell Culture & Transduction**
- Create tasks for each cell line:
  - `Thaw and expand MOLM-13 cells`
  - `Thaw and expand OCI-AML3 cells`
  - `Optimize lentiviral transduction conditions`
- Create experiment: `Lentiviral Transduction Optimization`
  ```
  Hypothesis: MOI of 0.3 achieves >90% transduction efficiency
  with <5% cytotoxicity in AML cell lines.
  Protocol: Seed 5e5 cells/well in 6-well plates. Add lentivirus
  at MOI 0.1, 0.3, 0.5, 1.0. Measure GFP+ by flow cytometry
  at 72h. Cell viability by CellTiter-Glo.
  ```
- Link tasks to this experiment so the Kanban board reflects
  experiment progress.

**Phase: Selection & gDNA Extraction**
- Create experiment: `Puromycin Selection Time Course`
  ```
  Protocol: 48h post-transduction, add 2 μg/mL puromycin.
  Culture for 14 days, replace media every 3 days.
  Collect genomic DNA at day 7 and day 14 using Qiagen DNeasy.
  ```
- Entry: **Result** — "Day 7 gDNA: 12 μg from MOLM-13,
  15 μg from OCI-AML3. Day 14: 8 μg from MOLM-13
  (cell loss due to toxicity), 14 μg from OCI-AML3."
- Attach the Bioanalyzer trace as an attachment.

**Phase: NGS Library Prep**
- Create task: `PCR amplify integrated gRNAs and add barcodes`
- Create task: `Run on NextSeq 2000, PE150, 20M reads/sample`
- Use **AI Assist** to draft the methods:
  - "Generate a methods section for NGS library preparation
    from gDNA using a two-step PCR protocol."
  - The AI outputs a publication-ready methods paragraph
    with primer sequences and thermocycling conditions.

**Phase: Data Analysis**
- Use **Research Tools → Generate Hypothesis**:
  - Topic: "Genes whose knockout confers resistance to
    chemotherapy in AML"
  - The AI suggests hypotheses linking specific pathways
    (BCL2, MCL1, FLT3) to drug resistance mechanisms.
- Use the **Auto Figure Generator** on the experiment:
  - It produces a volcano plot of enriched/depleted gRNAs
    and a heatmap of top hits across replicates.

**Phase: Validation**
- Create experiment: `Individual gRNA Validation in MOLM-13`
  ```
  Hypothesis: Knockout of top 5 hit genes (BCL2L1, MCL1,
  DOT1L, KAT6A, RUNX1) confirms screen results.
  Protocol: Transduce with individual gRNAs, measure
  proliferation over 7 days by CellTiter-Glo.
  ```
- Entry: **Result** — "BCL2L1 knockout confirmed:
  significant proliferation defect (p < 0.001, t-test).
  DOT1L knockout: moderate effect (p < 0.05)."

**AI features particularly useful for wet labs:**
- **Figure Generator** produces publication-ready analysis code
  from sequencing data
- **Citations Verification** checks references against PubMed
- **AI Assist** writes methods sections from protocols
- **Experiment entries** record lab notebook data in real time

---

### Economics Studies

Economics research involves model building, data collection (surveys,
public datasets), econometric analysis, and policy evaluation.
Projects are often theoretical or computational rather than wet-lab.

**Example: Impact of Minimum Wage on Informal Employment in Turkey**

*PI: Dr. Ahmet Gül, Department of Economics*

**Project Setup:**
1. Click **+ New Project** → Start from blank (no template).
2. Create custom phases:
   - Literature Review & Theoretical Framework
   - Data Collection
   - Econometric Analysis
   - Robustness Checks
   - Policy Implications
   - Paper Writing

**Phases in Action:**

**Phase: Literature Review & Theoretical Framework**
- Use **Research Tools → Literature Review**:
  - Topic: "Minimum wage effects on informal employment in
    developing countries"
  - The AI produces a structured review covering:
    - Neoclassical vs. institutional approaches
    - Key papers: Card & Krueger (1994), Neumark & Wascher
    - Empirical evidence from Latin America and Turkey
    - Research gap: limited panel data studies for Turkey
      post-2016 minimum wage reform
  - The review is saved as an experiment entry for reference.
- Create experiment: `Theoretical Model: Minimum Wage & Informality`
  ```
  Hypothesis: A segmented labor market model predicts that
  minimum wage increases lead to a substitution effect toward
  informal employment in sectors with low enforcement.
  Protocol: Develop a search-and-matching model with formal
  and informal sectors. Calibrate using TURKSTAT data.
  ```
- Use **AI Assist** to draft the theoretical framework for the
  paper's introduction.

**Phase: Data Collection**
- Create tasks for each dataset:
  - `Download TURKSTAT Household Labor Force Surveys 2014-2024`
  - `Obtain SGK social security registration data`
  - `Merge and clean panel dataset`
- Create experiment: `Panel Dataset Construction`
  ```
  Entry: Note
  "HLFS 2014-2024: 1.2M observations, 12 yearly waves.
  Variables: employment status, sector, wage, age, gender,
  education, region. Merged with SGK at province level.
  Missing: 3.2% of wage observations (imputed using
  multiple imputation with chained equations)."
  ```
- For large datasets, upload the processed .dta or .csv as an
  **Attachment**.

**Phase: Econometric Analysis**
- Create experiments for each model specification:
  ```
  Experiment: Baseline DiD Estimation
  Hypothesis: The 2016 minimum wage increase (30% nominal)
  led to a 2-4 percentage point increase in informal employment
  among low-skilled workers.
  Protocol: Difference-in-differences with 2014-2015 as
  pre-treatment period and 2017-2019 as post-treatment.
  Control group: high-skilled workers (wage > 2x minimum).
  Covariates: age, gender, education, region, GDP growth.
  ```
  - Entry: **Result** — "DiD coefficient: 0.031 (SE = 0.008,
    p = 0.002). ATT = 3.1 pp increase in informality.
    Robust to province fixed effects (0.028, p = 0.004)."

  ```
  Experiment: Heterogeneity Analysis by Region
  Entry: Result
  "East Anatolia: 4.8 pp increase (p = 0.001)
  Marmara: 1.2 pp increase (p = 0.23, not significant)
  Interpretation: Effect is driven by regions with
  weaker enforcement capacity."
  ```
- Use **AI Assist** on each experiment to generate econometric
  methods descriptions for the paper.
- Use **Research Tools → Methodology Validation**:
  - Describe: "We use a staggered DiD with multiple treatment
    periods. Standard errors are clustered at province level."
  - The AI checks for: parallel trends assumption, two-way
    fixed effects bias, alternative clustering strategies.

**Phase: Robustness Checks**
- Create experiment tasks:
  - `Placebo test: assign fake treatment year 2014`
  - `Alternative control group: workers in formal sector only`
  - `Synthetic control method`
  - `Remove Istanbul from the sample`
- Each robustness check is a separate experiment with clear
  hypothesis and result entries.

**Phase: Paper Writing**
- Create **Publication**: `Minimum Wage and Informal Employment:
  Evidence from Turkey's 2016 Reform`
- Use **AI Draft → Results** — the AI reads all experiment
  entries and generates a structured results section with
  numbers, tables, and interpretations.
- Use **AI Draft → Introduction** — the AI incorporates the
  literature review to set up the research gap.
- Before submission, use **Research Tools → Verify Citations**
  to check that all economic citations are real.

**Platform features particularly relevant for economics:**
- **Data-heavy experiments** with large CSV/Stata attachments
- **AI literature reviews** that search economic databases
- **Methodology validation** checks econometric assumptions
- **Hypothesis generation** produces testable economic models
- **Publications** can include working paper series and
  conference presentations

---

### Wireless & Electronic Studies

Engineering research in wireless communications and electronics involves
simulation, hardware prototyping, signal processing, and standards
compliance. Projects span from theoretical information theory to
physical-layer implementation.

**Example: 6G mmWave Beamforming with Reconfigurable Intelligent Surfaces**

*PI: Dr. Elif Kaya, Electrical and Electronics Engineering*

**Project Setup:**
1. Click **+ New Project** → **ML Research** template (since it
   involves simulation and optimization).
2. Name: `RIS-Assisted mmWave Beamforming for 6G Networks`
3. Phases:
   - Literature Review & Standards Survey
   - Channel Modeling & Simulation
   - Algorithm Development
   - Hardware Prototyping
   - Over-the-Air Testing
   - Performance Evaluation
   - Paper Writing & Patent Filing

**Phases in Action:**

**Phase: Literature Review**
- Use **Research Tools → Literature Review**:
  - Topic: "Reconfigurable Intelligent Surfaces for mmWave
    beamforming 2023-2026"
  - The AI produces a structured review organized by:
    - Channel estimation methods for RIS
    - Passive vs. active beamforming
    - Prototype implementations (testbeds)
    - Standardization in 3GPP Release 19
  - Saved as an experiment entry for the project.

**Phase: Channel Modeling & Simulation**
- Create experiment: `Ray-Tracing Channel Model for Urban Campus`
  ```
  Hypothesis: A 3D ray-tracing model with RIS elements placed
  on building facades achieves 15 dB median SNR gain over
  non-line-of-sight (NLOS) baseline at 28 GHz.
  Protocol: Use Wireless InSite or Sionna RT. Create 3D model
  of ITU campus. Place RIS at 3 candidate locations.
  Simulate 1000 random user positions. Metrics: SNR, delay
  spread, spatial correlation.
  ```
- Create tasks:
  - `Build 3D environment model in Blender`
  - `Configure Sionna RT simulation pipeline`
  - `Run baseline NLOS simulations (no RIS)`
  - `Run RIS-assisted simulations for 3 placements`
- Entry: **Result** — "RIS at Location B (Library facade):
  median SNR gain = 17.3 dB over NLOS. Delay spread reduced
  from 142 ns to 58 ns. Spatial correlation: 0.32 (acceptable
  for hybrid beamforming)."
- Attach the simulation output (.h5 or .mat files).

**Phase: Algorithm Development**
- Create experiments for each algorithm:
  ```
  Experiment: Deep Learning-Based Channel Estimation
  Hypothesis: A CNN-LSTM architecture achieves NMSE < 0.01
  with 75% pilot overhead reduction compared to LS estimation.
  Protocol: Generate 100k channel realizations from ray-tracing.
  Train CNN-LSTM with 80/10/10 split. Compare against LS, MMSE,
  and OAMP-Net baselines.
  ```
  ```
  Experiment: Hybrid Beamforming Optimization
  Hypothesis: An alternating minimization approach with
  manifold optimization achieves 95% of fully-digital
  beamforming spectral efficiency with 4 RF chains.
  ```
- Link algorithm experiments to the Channel Modeling experiment
  as dependencies (hard dependency).

**Phase: Hardware Prototyping**
- Create tasks:
  - `Design RIS unit cell: PIN diode-based phase shifter`
  - `Fabricate 8x8 RIS prototype on Rogers 5880 substrate`
  - `Design FPGA-based beamforming controller`
- Create experiment: `RIS Unit Cell Characterization`
  ```
  Protocol: Measure S11, phase shift, insertion loss from
  26-30 GHz using VNA. Control PIN diode bias voltage.
  ```
  - Entry: **Result** — "Unit cell achieves 360° phase
    range with 5-bit resolution. Insertion loss: 1.8 ±
    0.3 dB. Return loss > 15 dB across 27-29 GHz band."
  - Attach the measured S-parameter files (.s2p).

**Phase: Over-the-Air Testing**
- Create experiment: `OTA Test: Indoor Corridor Scenario`
  ```
  Hypothesis: RIS-assisted link achieves 200 Mbps at 100m
  range, 3x improvement over NLOS without RIS.
  Protocol: USRP X310 TX at 28 GHz. RIS on corridor wall.
  RX at 20, 50, 100m. Sweep RIS phase configuration.
  Measure: RSSI, EVM, throughput.
  ```
  - Entry: **Result** — "At 50m: RIS ON: 340 Mbps (64-QAM,
    EVM = -28 dB). RIS OFF (NLOS): 85 Mbps (16-QAM,
    EVM = -22 dB). Throughput gain: 4x."
  - Attach the spectrum analyzer screenshots.

**Phase: Performance Evaluation & Paper Writing**
- Use **Auto Figure Generator** on the OTA experiment:
  - Generates a comparison plot: RIS-ON vs RIS-OFF throughput
    vs distance, with shaded confidence bands.
  - Generates a constellation diagram comparison.
- Create **Publication**: `RIS-Assisted mmWave Communication:
  From Simulation to Hardware Demonstration`
- Use **AI Draft → Results** to incorporate simulation and
  measurement results.
- Use **AI Draft → Methods** for the hardware prototype and
  test setup descriptions.
- Consider creating a **Patent** task:
  - Use **AI Assist**: "Draft a patent disclosure for a
    reconfigurable intelligent surface with deep
    learning-based channel estimation."

**Platform features particularly relevant for wireless/electronics:**
- **Attachment entries** handle measurement files (.s2p, .mat, .h5)
- **Task dependencies** link algorithm→simulation→hardware flow
- **Experiments** track both simulation and measurement results
- **AI Figure Generator** creates publication-ready comparison plots
- **Methodology validation** checks experimental design rigor
- **Patent drafting** can be initiated through AI Assist

---

### Bioimaging & Connectomics

Bioimaging research generates large volumetric datasets from electron
microscopy (EM), light-sheet microscopy, and clinical MRI/CT. Managing
annotation workflows across Terabytes of image data is a central challenge.
The platform integrates with annotation tools: **CVAT** (2D/3D image and
video annotation) and **WebKnossos** (large-scale 3D EM annotation).

**Example 1: Connectomics — Mapping Synaptic Connectivity in Drosophila**

*PI: Dr. Can Öztürk, Neuroscience Department*

**Project Setup:**
1. Click **+ New Project** → **Life Science** template.
2. Name: `Drosophila Optic Lobe Connectome: Synaptic Resolution`
3. Phases:
   - Sample Preparation & EM Imaging
   - Image Stitching & Alignment
   - Segmentation & Proofreading (WebKnossos)
   - Synapse Detection & Annotation (CVAT)
   - Circuit Reconstruction
   - Graph Analysis & Discovery
   - Paper Writing

**Phases in Action:**

**Phase: Sample Preparation & EM Imaging**
- Create task: `Dissect and stain Drosophila optic lobe`
- Create task: `SBEM imaging at 4 nm resolution`
  - Description: "Serial block-face EM. 2,000 sections at
    4 nm/pixel. Expected dataset: 2 TB per sample."
- Create experiment: `EM Image Quality Assessment`
  - Entry: **Result** — "2,100 sections acquired. 4 nm
    isotropic. 12 misaligned sections (0.6%) flagged for
    manual correction. Overall quality: excellent."
  - Attach a representative section image.

**Phase: Image Stitching & Alignment**
- Create experiment: `Section Alignment Pipeline`
  ```
  Protocol: Cross-correlation-based alignment using IMOD.
  Fine alignment with elastic warping in TrakEM2.
  ```
  - Entry: **Result** — "RMS alignment error: 2.1 nm.
    Aligned volume: 5120 x 5120 x 2100 voxels."
- Attach the alignment transformation parameters as a file.

**Phase: Segmentation & Proofreading (WebKnossos)**

This is the critical annotation phase. WebKnossos handles TB-scale
3D EM data with skeleton tracing and volumetrics.

1. Create task: `Import aligned volume into WebKnossos`
   - Description: "Convert to WKW format. Set up
     WebKnossos dataset with 8x8x8 nm downsampling layers."
2. Create task: `Train initial CNN segmentation model`
   - Description: "Manually label 50x50x50 voxel region
     for training data. Train 3D U-Net in WebKnossos.
     Expected: initial membranes and mitochondria."

3. Create experiment: `Automated Segmentation & Proofreading`
   ```
   Hypothesis: A 3D U-Net with human proofreading achieves
   > 95% junction-recall for neuron reconstruction in
   Drosophila optic lobe EM.
   Protocol: 
   1. Run WebKnossos built-in CNN on full volume
   2. Divide into 100 blocks for distributed proofreading
   3. Assign 3 annotators per block
   4. Merge and resolve conflicts
   ```
   - Entry: **Note** — "Full volume segmented in 48h on
     4x A100 GPUs. Initial merge error rate: 8%.
     Proofreading progress: 45/100 blocks complete.
     Current recall: 0.93, precision: 0.89."
   - WebKnossos annotation state exported as WKW and
     attached for reproducibility.

4. Link task: `Proofread blocks 1-25` — assign to PhD student A
5. Link task: `Proofread blocks 26-50` — assign to PhD student B
6. Use **Task Dependencies**: Proofreading tasks depend on
   segmentation completion (hard dependency).

**Phase: Synapse Detection (CVAT)**

CVAT handles 2D slice-by-slice annotation and video sequences.
Here it is used for synapse identification on EM sections.

1. Create task: `Set up CVAT project for synapse annotation`
   - Labels: `synapse_ribbon`, `postsynaptic_density`,
     `active_zone`, `mitochondrion`, `vesicle_cluster`
   - Import 200 key EM sections (every 10th section) as a
     CVAT task
   - Assign to 2 domain experts

2. Create experiment: `Synapse Detection Performance`
   ```
   Hypothesis: A Mask R-CNN trained on CVAT annotations
   detects 90% of ribbon synapses in Drosophila EM.
   Protocol: 
   1. Export CVAT annotations in COCO format
   2. Train Mask R-CNN on 160 training images
   3. Validate on 40 test images
   ```
   - Entry: **Result** — "mAP@50: 0.87. Synapse ribbon AP:
     0.91. Postsynaptic density AP: 0.83. Vesicle cluster
     AP: 0.79."
   - Attach the trained model as an experiment attachment.

3. Export CVAT annotations → download COCO JSON → attach
   to experiment entry for full provenance.

**Phase: Circuit Reconstruction**
- Create experiment: `Synaptic Partner Identification`
  ```
  Protocol: Combine WebKnossos neuron skeletons with
  CVAT synapse locations. Compute synapse-partner
  adjacency matrix. Filter by cleft distance < 30 nm.
  ```
  - Entry: **Result** — "Reconstructed 847 neurons with
    12,456 identified synapses. 42% on T1 neurons,
    31% on Tm neurons, 27% on amacrine cells.
    Columnar organization confirmed."
  - Attach the adjacency matrix (GraphML) and connectivity
    graph visualization.
- Use **AI Assist**: "Summarize the circuit reconstruction
  findings for the Results section: number of neurons,
  synapses, connectivity motifs identified."

**Phase: Graph Analysis & Discovery**
- Create experiment: `Network Motif Analysis`
  ```
  Hypothesis: The Drosophila optic lobe contains over-
  represented feedforward motifs (3-neuron chains)
  compared to random networks.
  Protocol: Enumerate all 3-node motifs. Compare against
  1,000 Erdos-Renyi random graphs with same degree sequence.
  Z-score for motif significance.
  ```
  - Entry: **Result** — "Feedforward motif: z = 5.2,
    p < 0.001. Feedback motif: z = 1.2, p = 0.11.
    Reciprocal motif: z = 3.8, p = 0.002."
- Use **Figure Generator** to create a motif significance
  bar plot from the data.

**Example 2: Clinical MRI Segmentation with CVAT 3D + WebKnossos**

*PI: Dr. Fatma Aksoy, Department of Radiology*

**Project Setup:**
1. Click **+ New Project** → **Medical Research** template.
2. Name: `Brain Tumor Segmentation with Multi-Modal MRI`
3. Phases:
   - IRB & Data Collection (PACS)
   - Preprocessing & Registration
   - Annotation (CVAT 3D)
   - Model Training
   - Clinical Validation
   - Paper Writing

**Phases in Action:**

**Phase: Data Collection from PACS**
- Create experiment: `PACS Query — Brain MRI, 2022-2026`
  ```
  Protocol: DICOM C-FIND query for Brain MRI studies.
  Modalities: T1, T1-CE, T2, FLAIR, DWI.
  Inclusion: Histopathology-confirmed glioma.
  ```
  - Entry: **Result** — "350 patients, 1,400 MRI series,
    280 GB total. Exporting as NIfTI after
    de-identification."
  - Create sub-tasks for each preprocessing step:
    `Bias field correction (N4ITK)`,
    `Skull stripping (HD-BET)`,
    `Registration to MNI space`

**Phase: Annotation with CVAT 3D**
- Create task: `Set up CVAT 3D for tumor segmentation`
  ```
  Description: Import as DICOM or NRRD. Label tumor
  sub-regions: enhancing tumor, necrotic core, edema.
  Protocol: Two radiologists annotate independently,
  then consensus. Annotation per slice.
  ```
- Create experiment: `Inter-Rater Agreement Analysis`
  - Entry: **Result** — "Dice between R1 and R2: 0.89
    (enhancing), 0.85 (necrotic), 0.82 (edema).
    Consensus set: Dice with R1: 0.94, R2: 0.93."
- CVAT exports: DICOM-SEG + COCO for 3D → attached to
  the experiment for downstream ML.

**Phase: Annotation with WebKnossos (for high-res 3D)**
- If you have isotropic or near-isotropic volumes (e.g.,
  3D FLAIR at 1 mm³), WebKnossos offers superior 3D
  annotation with real-time GPU volume rendering.
- Create task: `Import high-res FLAIR into WebKnossos`
- Create task: `Annotate 30 volumes in WebKnossos`
  - Use WebKnossos's skeleton and volume annotation tools
    for precise tumor boundary delineation
  - WebKnossos's AI-assisted segmentation can be used
    as a first pass before manual refinement

**Phase: Model Training**
- Create experiment: `nnU-Net BraTS-style Tumor Segmentation`
  ```
  Protocol: 5-fold cross-validation. Input: 4 MRI
  modalities. Output: 3 tumor sub-regions.
  Loss: Dice + CE. Post-processing: remove
  connected components < 1000 mm³.
  ```
  - Entry: **Result** — "Average Dice: 0.92 (whole tumor),
    0.88 (tumor core), 0.83 (enhancing). HD95: 3.2 mm.
    Inference time: 12s per volume on RTX 4090."

**Phase: Clinical Validation**
- Create experiment: `Comparison with Radiologist Report`
  ```
  Hypothesis: AI segmentation volumes correlate with
  radiologist planimetric measurements within 5% error.
  Protocol: Bland-Altman analysis of tumor volumes.
  ```
  - Entry: **Result** — "Mean volume difference: 2.3 mL.
    Limits of agreement: -4.1 to 8.7 mL. Pearson r = 0.97."

### Using CVAT and WebKnossos Together: Decision Guide

| Scenario | Recommended Tool | Why |
|---|---|---|
| 2D medical image classification (fundus, X-ray) | **CVAT** | Built-in label interface, COCO export, tracker support |
| 3D medical segmentation (MRI, CT) | **CVAT 3D** | DICOM import, multi-frame annotation, inter-rater workflow |
| Large EM volume segmentation (> 100 GB) | **WebKnossos** | Web-based, supports TB-scale data, AI-assisted segmentation |
| Skeleton tracing in EM | **WebKnossos** | Native skeleton annotation with node editing |
| Synapse/object detection on 2D EM slices | **CVAT** | Polygon and bounding box, COCO export for DL training |
| Video microscopy (time-lapse, calcium imaging) | **CVAT** | Video tracking, interpolation, automatic object tracking |
| Multi-modal registration validation | **Both** | Use CVAT for 2D overlay, WebKnossos for 3D volume alignment check |

**Key integrations for bioimaging:**
- **CVAT annotation exports** (COCO, YOLO, DICOM-SEG, CVAT XML)
  stored as experiment attachments
- **WebKnossos** WKW datasets and skeleton files tracked via
  experiment entries
- **Task dependencies** enforce annotation → model training →
  validation pipeline ordering
- **Large file support** via Garage S3 storage (up to 50 MB per
  attachment, can be extended)
- **AI Assist** helps write methods sections for imaging pipelines
- **Figure Generator** creates segmentation overlay visualizations
  and Dice coefficient bar plots

---

### Quick Comparison: Feature Use by Domain

| Feature | Clinical | EHR/PACS | Wet Lab | Economics | Wireless | Bioimaging |
|---|---|---|---|---|---|---|
| **Medical template** | ✓ Best fit | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Life Science template** | ✗ | ✗ | ✓ Best fit | ✗ | ✗ | ✓ |
| **ML Research template** | ✗ | ✓ (DL focus) | ✗ | ✗ | ✓ | ✓ (if ML-heavy) |
| **No template (blank)** | ✗ | ✗ | ✗ | ✓ Best fit | ✗ | ✗ |
| **IRB module** | ✓ Essential | ✓ Essential | ✓ If needed | ✗ | ✗ | ✓ If clinical |
| **AI Hypothesis Gen** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **AI Methodology Validation** | ✓ (trial design) | ✓ (data pipeline) | ✓ (protocol) | ✓ (identification) | ✓ (experimental) | ✓ (annotation QC) |
| **AI Literature Review** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **AI Assist (experiments)** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Figure Generator** | ✓ (forest plots) | ✓ (ROC, Bland-Altman) | ✓ (volcano, heatmap) | ✓ (coefficient plots) | ✓ (constellation) | ✓ (segmentation overlays) |
| **Grant Writer** | ✓ (TÜSEK, NIH) | ✓ (TÜSEK, NIH) | ✓ (TÜBİTAK) | ✓ (TÜBİTAK) | ✓ (NSF) | ✓ (ERC, NIH) |
| **Experiment Attachments** | ✓ (CRFs, consent) | ✓ (DICOM, NIfTI) | ✓ (gels, traces) | ✓ (datasets, .dta) | ✓ (s2p, mat) | ✓ (WKW, COCO, NRRD) |
| **Task Dependencies** | ✓ (sequential) | ✓ (pipeline) | ✓ (pipelines) | ✓ (robustness) | ✓ (sim→HW) | ✓ (annotate→train→validate) |

---

## 9. Grants & Conferences

### Grants

Track research funding applications and awards:

**Creating a Grant:**
1. Navigate to **Grants** → **+ New Grant**.
2. Enter:
   - **Title** (required)
   - **Funder** (e.g., TÜBİTAK, NSF, NIH, ERC)
   - **Amount** and **Currency**
   - **Start/End dates**
   - **Status**: Draft, Submitted, Under Review, Awarded, Rejected, Active, Closed
3. Click **Create**.

**Grant Status Workflow:**
- **Draft** → Preparing the application
- **Submitted** → Under agency review
- **Under Review** → Being evaluated
- **Awarded** → Funding approved
- **Active** → Funding received, project ongoing
- **Closed** → Project completed
- **Rejected** → Not funded

### Conferences

Track conference deadlines and submissions:

**Creating a Conference Entry:**
1. Navigate to **Conferences** → **+ New Conference**.
2. Enter:
   - **Name** (required)
   - **Submission Deadline**
   - **Conference Dates**
   - **Location**
   - **Status**: Considering, Preparing, Submitted, Accepted, Rejected,
     Presented
3. Click **Create**.

---

## 10. IRB / Ethics Approvals

Manage institutional ethics approvals for research involving human subjects,
animals, or sensitive data.

### Creating an IRB Protocol

1. Navigate to **IRB** → **+ New IRB**.
2. Enter:
   - **Title** (required)
   - **Institution** (e.g., your university)
   - **Protocol Number**
   - **Approval Date** and **Expiry Date**
   - **Project** — Associate with a project
3. Click **Create**.

The IRB page lists all protocols with their approval status and expiry
dates, helping you ensure compliance.

---

## 11. Admissions Pipeline

Manage graduate student and researcher applications to your lab.

### Viewing Applications

Navigate to **Admissions** to see all applicants. Filter by status:
- **All** / **Submitted** / **Reviewing** / **Accepted** / **Rejected**

### Importing Applicants

Batch import from CSV or Excel:
1. Click **Import**.
2. Select a file with columns for applicant information.
3. The system parses and creates admission records.

### Reviewing an Applicant

Click an applicant to view their full profile:
- **Personal Info** — Name, email, phone, university, department
- **Supervisor** — Proposed advisor
- **Service Areas** — Research interests
- **Grant Context** — Associated funding information

### Decision Workflow

1. **Assign Reviewer** — Add internal review notes.
2. **Accept** — Optionally add acceptance notes. Creates a user account
   automatically.
3. **Reject** — Requires a rejection note for record-keeping.
4. **Financial Aid** — Set financial aid percentage for accepted applicants.

---

## 12. Lab Wiki

Each lab has a wiki for shared knowledge, protocols, and documentation.

### Creating a Wiki Page

1. Navigate to your lab → **Wiki** tab.
2. Click **+ New Page**.
3. Enter:
   - **Title** (required)
   - **Content** — Markdown-formatted text
   - **Tags** — Keywords for organization
4. Click **Create**.

### Editing a Wiki Page

1. Open the wiki page.
2. Click **Edit** to modify title and content.
3. Markdown is rendered live as you type.
4. Click **Save** to update.

Wiki pages are searchable and tagged for easy reference.

---

## 13. Research Impact

Track your lab's research impact using Semantic Scholar citation data.

### Accessing Impact Metrics

1. Navigate to your lab → **Impact** tab.
2. The dashboard shows:
   - **Total Publications** — Number of publication records
   - **S2 Matched** — Publications found in Semantic Scholar
   - **Total Citations** — Sum of all citations
   - **h-index** — Hirsch index based on citation counts
   - **Avg Citations/Paper** — Mean citations per publication

### Citation Details

The publication table shows per-paper metrics:
- **Title** and **Status**
- **Citation Count**
- **Influential Citations** — Citations from highly influential papers
- **Venue**
- **Year**
- **Open Access** status

Data is refreshed automatically from Semantic Scholar.

---

## 14. MCP Servers & Memory

### MCP Server Marketplace

MCP (Model Context Protocol) servers extend the AI agent's capabilities:

1. Navigate to **MCP** to browse the marketplace.
2. Browse available servers by tag (data, search, code, etc.).
3. Click **Install** to add a server to your instance.
4. Installed servers are available to the AI agent for tool use.

### Memory & Observations

The memory system records AI agent observations for cross-session context:

- **List Observations** — View all observations for a project.
- **Search Observations** — Find relevant observations by keyword.
- **Record Observation** — Manually add an observation with title and body.
- **Link Observations** — Create relationships between observations.

This enables the AI to maintain context across multiple interactions with
your project.

---

## 15. Reports & Analytics

### Project Report

From any project, click **Report** to generate a printable report with:
- Task completion statistics (percentage)
- Experiment status distribution (donut chart)
- Priority breakdown
- Team overview
- Experiments summary

The report is formatted for A4 print-to-PDF.

### Global Report

Navigate to **Reports** for cross-project aggregate analytics:
- Bar charts comparing completion across projects
- Total task counts
- Overall project statistics
- Status distributions

### PI Analytics

Navigate to **Analytics** for Principal Investigator dashboards:
- Lab overviews with member counts
- Task/experiment/publication status breakdowns
- Publications over time (monthly bar chart)
- Mentorship statistics (co-authorship by lab members)

### Admin Dashboard

System administrators see cross-lab statistics:
- Total labs, users, projects, tasks, experiments
- Per-lab detail cards with member and project counts
- System health status

---

## 16. Settings & Administration

### Profile Settings

Navigate to **Profile** to:
- View your username and admin status
- Toggle between light and dark theme
- Log out of the platform

### Model Settings (Admin)

Navigate to **Settings** → **Model Selection**:
- Browse available LLM models by provider
- Switch the active model used by AI features
- View the current model's capabilities

### System Prompt (Admin)

View the current system prompt used by the AI agent. This controls the
agent's behavior and available tools.

### User Management (Admin)

Navigate to **Users** to:
- View all registered users
- Create new user accounts (username, password, email)
- Delete users

### Health Check

Navigate to **Health** to verify:
- System component status
- AI service availability
- Skill configuration

---

## Quick Reference

### Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| New Task | `N` (on board) |
| Search | `Ctrl+K` or `Cmd+K` |
| Save | `Ctrl+S` or `Cmd+S` |
| Cancel | `Esc` |

### Common Workflows

**Starting a new research project:**
1. Create Lab → 2. Create Project → 3. Set up phases →
4. Create tasks → 5. Run experiments → 6. Draft paper →
7. Submit to journal → 8. Track in Publications

**Using AI tools:**
1. Set up project context → 2. Generate hypothesis →
3. Validate methodology → 4. Run experiments →
5. AI-draft paper sections → 6. AI review → 7. Submit

### Support

For technical support or feature requests, contact your system
administrator or the development team.

---

*EvoScientist PM — Research Project Management for University Labs*

## Academic Supervision

EvoScientist now includes a weekly supervision loop for professors and students.

### Getting started by role

**Students**
1. Open **HOME** — your primary actions are Weekly update, My journey, and tasks.
2. Each week, open **WEEKLY** and update every action point (progress %, blockers, help flags, next step).
3. Add a short summary (accomplished / next focus / support needed) and **Submit for review**.
4. Check **JOURNEY** for graduation readiness against your programme requirements.

**Professors**
1. Open **DASHBOARD** for group KPIs: submitted reports, reviews waiting, help requests, high risk.
2. Use **MEETING** week-by-week to review each student, record attendance (on time / late / excused / absent), grant extensions, and save feedback.
3. Capture "action for me" follow-ups so promised reviews stay on your task list.
4. **REPORTS** filters all weekly submissions by status, review state, and risk.

**Admins**
1. In **USERS**, set each account's role to `student`, `professor`, or `admin`.
2. Assign supervisors under the supervision API (or ask a professor to claim students).
3. Define programme rules in **REQUIREMENTS** (research items such as journal or conference papers, and human-confirmed milestones).
4. Use **ADMISSIONS** to accept applicants into the pipeline.

### Weekly cadence

| When | Student | Professor |
|---|---|---|
| Before the meeting | Submit weekly update | — |
| During the meeting | Attend (recorded) | Record attendance, review report |
| After the meeting | Apply feedback | Grant extensions, create follow-up tasks |

Meeting schedule is versioned per professor — changing the day does not rewrite past weeks.

### Graduation readiness

**JOURNEY** shows a live readiness percentage from required rules (journal/conference paper counts) plus the student's degree context and thesis title. Milestone rules stay open until a human confirms them. Remove on **REQUIREMENTS** archives a rule — it never deletes student progress.

Course credits, GPA, and transcripts are deliberately **not** tracked: this platform covers publication work, and the registrar owns the transcript.
