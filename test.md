# 💪 Kuat Bersama Telkom – Talent Matching & Network Analyzer
 **Kuat Bersama Telkom** is a data-driven web application designed to help Telkom Indonesia optimize its internal talent allocation. By combining text embeddings, clustering, and co-worker detection, the app identifies and ranks the best candidates for specific use cases.
 ---
 ## 🎯 Purpose
 This application is built to support:
 * **Skill-based talent matching** for specific job requirements or use cases.
* **Internal collaboration network analysis** through historical co-assignment data.
* **Data-driven recommendations** for talent allocation based on multiple scoring factors.
 ---
 ## 🧠 How It Works
 ### 1. **Upload Data**
 Users upload several data files, including:
 * Skill Inventory (`df_skillinv`)
* Use Case Requirements (`df_ureq`)
* Employee Info (`df_talent`)
* Evaluation Scores (`df_eval`)
* Work History (`df_hist`)
* Assignment Data (`df_assign`)
 These datasets form the basis for the entire recommendation system.
 ---
 ### 2. **Talent Matching to Use Case**
 * Uses **sentence embeddings** (`all-MiniLM-L6-v2` from Sentence Transformers) to compare job descriptions to employee skillsets.
* Calculates **cosine similarity** to assess role fit.
* Filters and aggregates candidates based on similarity scores and skill proficiency.
 ---
 ### 3. **Clustering Talent by Skills**
 * Reduces high-dimensional skill features using **PCA**.
* Applies **KMeans clustering** to identify natural groupings of talents.
* Helps identify clusters of employees with similar capabilities.
 ---
 ### 4. **Scoring and Ranking**
 Each candidate is scored based on:
 * Skill match (average skill score)
* Evaluation score
* Work experience (in months)
* Historical project count (`job_count`)
* Bonus weight if role alignment is exact
 Final score is calculated using a customizable weighted formula:
 ```
final_score = (a × skill_score) + (b × evaluation_score) + (c × job_count)
```
 and multiplied by a role alignment bonus if applicable.
 ---
 ### 5. **Co-worker Detection**
 * Builds a **collaboration graph** based on:
  * Shared squads/products in `df_assign`
  * Shared project history in `df_hist`
* Calculates connection strength (weight) between talents.
* Suggests potential teammates for key candidates.
 ---
 ### 6. **Final Recommendation & Export**
 * Top N candidates are selected per role or user query.
* Co-worker recommendations are included.
* All results can be downloaded as Excel files.
 ---
 ## 🧾 Features
 | Feature                     | Description                                                             |
| --------------------------- | ----------------------------------------------------------------------- |
| 🔍 Talent-Use Case Matching | Finds best-fit candidates using text embeddings + cosine similarity     |
| 📊 Clustering Analysis      | Groups similar talents using PCA + KMeans                               |
| 🧮 Weighted Scoring         | Combines skill, evaluation, and experience into final scores            |
| 🤝 Co-worker Mapping        | Detects internal collaboration networks to inform assignment strategies |
| 📥 Upload-Driven Workflow   | Flexible input via Excel files                                          |
| 📤 Excel Export             | All results exportable as `.xlsx` for easy sharing                      |
| 🔧 Parameter Tuning         | Thresholds and weights adjustable through the UI                        |
| 👤 User-Based Talent Search | Accepts ad-hoc role/skill queries with instant recommendations          |
 ---
 ## 🛠️ Tech Stack
 * **Frontend:** Streamlit
* **Text Processing:** Sentence Transformers (MiniLM)
* **Clustering & ML:** scikit-learn
* **Data Handling:** pandas, NumPy
* **File Handling:** openpyxl, BytesIO
 ---
 ## 📂 Required Input Files
 All uploads must be in `.xlsx` format:
 * `df_skillinv` – Employee skill ratings
* `df_ureq` – Role or use case descriptions
* `df_talent` – Basic employee data (e.g. name, role, duration)
* `df_eval` – Performance or evaluation scores
* `df_hist` – Work/project history
* `df_assign` – Assignment data including tribe, product, squad
 ---
 ## 🚀 How to Run
 ```bash
streamlit run app.py
```
 Place the file in your working directory and make sure all dependencies are installed.
 ---
 ## ✅ Dependencies
 Install via pip:
 ```bash
pip install streamlit pandas numpy scikit-learn sentence-transformers openpyxl
```
 ---
 ## 🔐 Notes
 * This app does **not send any data externally**—it's designed to run in a **closed/internal network**.
* All scoring logic is fully visible and adjustable within the app UI.
 ---
 ## 👥 Author & Credits
 Developed by and for **Telkom Indonesia** internal Data & Talent Management teams.
