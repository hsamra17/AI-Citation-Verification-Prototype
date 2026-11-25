# AI-Citation-Verification-Prototype


## 1. Project overview and status

AI-generated responses can contain inaccurate or unsupported information, even when citations are provided. This prototype aims to encourage users to examine the evidence behind a response rather than relying on the presence of citations alone.

The developed prototype supports three prepared questions, citation inspection, Yes/No/Unsure feedback, website exclusion and restoration. Users can compare responses with prepared evidence summaries and open the original sources. Excluded website preferences are saved locally between application runs.

The responses are simulated, while the citations link to genuine sources. Some example claims are deliberately overstated for educational purposes and should not be treated as factual advice. The system does not generate live AI responses, retrieve sources automatically or perform automated fact-checking.

## 2. Technology stack

- **Python 3.14.10:** Handles question matching, feedback, response filtering and file management.
- **Gradio 6.32.0:** Provides the interactive user interface.
- **JSON:** Stores prepared responses, citation information and website exclusions.
- **VS Code:** Used for development and local testing.
- **Git and GitHub:** Used for version control and documenting significant development changes.

## 3. Installation and running

Install Python and Git before running the following commands in Windows Command Prompt:

```cmd
git clone https://github.com/hsamra17/AI-Citation-Verification-Prototype.git
cd AI-Citation-Verification-Prototype
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

Open the local URL displayed in the terminal, usually http://127.0.0.1:7860. No API key is required. Stop the application using Ctrl+C.

## 4. Project structure

| File or folder | Purpose |
|---|---|
| `app.py` | Interface and application logic. |
| `responses.json` | Prepared questions, answers and source details. |
| `excluded_sites.json` | Locally saved website preferences; created automatically if missing. |
| `requirements.txt` | Required Gradio dependency. |
| `.gitignore` | Rules for excluding unnecessary local files. |
| `Screenshots/` | Visual evidence of prototype interactions. |
| `README.md` | Project instructions and development record. |

## 5. Development record

The prototype was developed incrementally, with significant changes recorded through Git commits. The following table summarises the main decisions and their purpose.

| Stage | Changes and reasoning | Checks and evidence |
|---|---|---|
| Configuration and interface | Set up the environment and basic Gradio layout to establish a working foundation. | Verified the Gradio installation and launched the interface locally. |
| Response dataset | Separated prepared questions and citations from application logic for easier maintenance. | Reviewed the JSON structure. |
| Question processing | Added normalised question matching and messages for unsupported inputs. | Tested three prepared questions, capitalisation, missing punctuation and invalid inputs. |
| Citation inspection | Introduced a side-by-side evidence panel to make comparison easier. | Inspected the exercise citation and checked the displayed evidence. |
| Feedback | Added Unsure alongside Yes and No to avoid forcing a judgement when evidence is unclear. | Feedback interaction screenshots. |
| Website management | Separated negative feedback from exclusion and added reversible preferences to maintain user control. | Exclusion, withheld response and restoration screenshots. |
| Error handling | Added data validation and clearer error messages to avoid silently ignoring preferences. | Unknown and empty question checks; additional file error checks recommended. |
| Usability and sources | Refined the layout and replaced illustrative sources with genuine links so users can inspect original material. | Final interface and citation screenshots; links should be checked before submission. |

[View the development commit history](https://github.com/hsamra17/AI-Citation-Verification-Prototype/commits/main/).

## 6. Testing and interaction evidence

Manual testing covered the exercise, caffeine and houseplant scenarios, including correct response selection, capitalisation and missing question marks. Empty and unrecognised questions also returned appropriate messages during development.

The [Screenshots folder](Screenshots/) contains visual evidence of the developed interactions. Further checks for persistence after restarting, malformed JSON and restoration confirmation can be repeated using the application. Screenshot evidence demonstrates interaction states rather than proving that the prototype improves users' ability to identify inaccurate information.

## 7. AI assistance and authorship

ChatGPT assisted with developing the storyboards, illustrating the proposed system architecture, discussing design choices and providing staged development guidance. GitHub Copilot assisted with implementing, debugging and refining the code and interface.

I directed the development in stages, reviewed suggested changes, manually interacted with the prototype and managed the GitHub commits. For example, I tested question matching using capital letters and invalid inputs, and reviewed the displayed evidence against the intended storyboard interaction. The design was refined to include an Unsure option and genuine source links rather than the initial illustrative domains.

## 8. Limitations and future improvements

The prototype supports only prepared questions and does not independently assess source reliability. Feedback is held in session state, while website exclusions use shared local storage intended for single-user use. Future improvements could include live source retrieval, individual user preferences and user evaluation to investigate whether the design improves citation assessment.
