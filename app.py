import json
from pathlib import Path

import gradio as gr


# Load prepared responses from the JSON file next to this Python file.
responses_file_path = Path(__file__).parent / "responses.json"
with responses_file_path.open(encoding="utf-8") as responses_file:
    response_dataset = json.load(responses_file)

prepared_examples = response_dataset["examples"]

# Create the local exclusion list on first run, then load saved domains.
excluded_sites_file_path = Path(__file__).parent / "excluded_sites.json"
if not excluded_sites_file_path.exists():
    excluded_sites_file_path.write_text("[]\n", encoding="utf-8")

with excluded_sites_file_path.open(encoding="utf-8") as excluded_sites_file:
    saved_excluded_domains = json.load(excluded_sites_file)

if not isinstance(saved_excluded_domains, list):
    raise ValueError("excluded_sites.json must contain a JSON list of website domains.")

excluded_site_domains = []
for saved_domain in saved_excluded_domains:
    if not isinstance(saved_domain, str) or not saved_domain.strip().rstrip("."):
        raise ValueError("Each excluded website domain must be a non-empty string.")
    cleaned_domain = saved_domain.strip().rstrip(".")
    if not any(
        existing_domain.rstrip(".").casefold() == cleaned_domain.casefold()
        for existing_domain in excluded_site_domains
    ):
        excluded_site_domains.append(cleaned_domain)

feedback_messages = {
    "Yes": "Feedback recorded: You believe this citation supports the response.",
    "No": "Feedback recorded: You believe this citation does not support the response.",
    "Unsure": "Feedback recorded: You are unsure whether this citation supports the response.",
}


def normalize_question_text(question):
    """Make questions comparable despite letter case, spacing, or trailing question marks."""
    return " ".join(question.split()).casefold().rstrip(" ?")


def normalize_domain(domain):
    """Compare website domains without being affected by letter case or a final dot."""
    return domain.strip().rstrip(".").casefold()


def save_excluded_site_domains():
    """Persist the current website exclusions as a JSON list."""
    excluded_sites_file_path.write_text(
        json.dumps(excluded_site_domains, indent=2) + "\n",
        encoding="utf-8",
    )


def format_excluded_sites():
    """Build the text shown in the website management section."""
    if not excluded_site_domains:
        return "No websites are currently excluded."

    excluded_domain_list = "\n".join(
        f"- `{domain}`" for domain in excluded_site_domains
    )
    return f"Currently excluded domains:\n\n{excluded_domain_list}"


def reset_question_outputs(message, question):
    """Clear citation-related controls and state when there is no usable response."""
    return (
        message,
        "",
        None,
        "",
        "",
        gr.update(visible=False),
        "",
        gr.update(visible=False),
        None,
        question or "",
        "",
    )


def process_question(question):
    """Find a prepared response while excluding websites in the saved preference list."""
    if not question or not question.strip():
        return reset_question_outputs("Please enter a question.", question)

    normalized_user_question = normalize_question_text(question)
    excluded_domains = {
        normalize_domain(domain) for domain in excluded_site_domains
    }

    for example in prepared_examples:
        normalized_prepared_question = normalize_question_text(example["question"])
        if normalized_user_question == normalized_prepared_question:
            eligible_citations = [
                citation
                for citation in example["citations"]
                if normalize_domain(citation["website_domain"]) not in excluded_domains
            ]
            if not eligible_citations:
                if example["citations"]:
                    unavailable_message = (
                        "The simulated answer has been withheld because all citations "
                        "for this example come from excluded websites. Restore a "
                        "website in the Excluded Websites section and submit the "
                        "question again."
                    )
                else:
                    unavailable_message = (
                        "The simulated answer has been withheld because the prepared "
                        "example does not contain any citations."
                    )
                return reset_question_outputs(unavailable_message, question)

            selected_citation = eligible_citations[0]
            citation_summary = (
                "**Simulated teaching citation:** "
                f"{selected_citation['source_title']} "
                f"(`{selected_citation['website_domain']}`)"
            )
            return (
                example["simulated_answer"],
                citation_summary,
                selected_citation,
                "",
                "",
                gr.update(visible=False),
                "",
                gr.update(visible=False),
                None,
                question,
                "",
            )

    return reset_question_outputs(
        "That question is not recognised yet. Please try one of the three "
        "example questions listed above.",
        question,
    )


def inspect_citation(selected_citation, feedback_records):
    """Show citation evidence and any feedback already recorded for it."""
    if not selected_citation:
        return "", "", gr.update(visible=False)

    evidence_details = (
        "### Evidence preview\n\n"
        "**Simulated teaching material; not a live source.**\n\n"
        f"**Source title:** {selected_citation['source_title']}\n\n"
        f"**Website domain:** `{selected_citation['website_domain']}`\n\n"
        f"**Evidence preview:** {selected_citation['evidence_preview']}"
    )
    citation_id = selected_citation["citation_id"]
    previous_choice = (feedback_records or {}).get(citation_id)
    previous_feedback_message = feedback_messages.get(previous_choice, "")
    return evidence_details, previous_feedback_message, gr.update(visible=True)


def save_feedback(feedback_choice, selected_citation, feedback_records):
    """Save feedback by citation ID and show exclusion controls only after No."""
    if not selected_citation:
        return (
            "",
            feedback_records or {},
            "",
            gr.update(visible=False),
            None,
            "",
        )

    updated_feedback_records = dict(feedback_records or {})
    citation_id = selected_citation["citation_id"]
    updated_feedback_records[citation_id] = feedback_choice

    if feedback_choice == "No":
        website_domain = selected_citation["website_domain"]
        exclusion_prompt = (
            "**Would you like to exclude this website from future responses?**\n\n"
            "An unsupported citation does not necessarily mean the entire website "
            "is unreliable. Excluding a website is your preference, not proof that "
            "it is factually unreliable."
        )
        return (
            feedback_messages[feedback_choice],
            updated_feedback_records,
            exclusion_prompt,
            gr.update(visible=True),
            website_domain,
            "",
        )

    return (
        feedback_messages[feedback_choice],
        updated_feedback_records,
        "",
        gr.update(visible=False),
        None,
        "",
    )


def record_yes_feedback(selected_citation, feedback_records):
    return save_feedback("Yes", selected_citation, feedback_records)


def record_no_feedback(selected_citation, feedback_records):
    return save_feedback("No", selected_citation, feedback_records)


def record_unsure_feedback(selected_citation, feedback_records):
    return save_feedback("Unsure", selected_citation, feedback_records)


def hide_evidence_preview():
    """Hide and clear the evidence preview while keeping the citation selectable."""
    return "", gr.update(visible=False)


def keep_website(pending_exclusion_domain):
    """Dismiss the exclusion prompt without changing the saved website list."""
    if not pending_exclusion_domain:
        return (
            gr.update(visible=False),
            None,
            "No website is selected to keep.",
        )

    confirmation_message = (
        f"Kept `{pending_exclusion_domain}`. It remains eligible for future "
        "responses; an unsupported citation alone does not make a website "
        "unreliable."
    )
    return gr.update(visible=False), None, confirmation_message


def refresh_question_after_exclusion(question, status_message):
    """Recheck the current question after an exclusion and refresh the site list."""
    (
        response_message,
        citation_summary,
        selected_citation,
        evidence_details,
        feedback_message,
        evidence_panel_update,
        exclusion_prompt,
        exclusion_controls_update,
        pending_exclusion_domain,
        current_question,
        _,
    ) = process_question(question)
    return (
        response_message,
        citation_summary,
        selected_citation,
        evidence_details,
        feedback_message,
        evidence_panel_update,
        exclusion_prompt,
        exclusion_controls_update,
        pending_exclusion_domain,
        current_question,
        status_message,
        format_excluded_sites(),
        gr.update(choices=excluded_site_domains, value=None),
        gr.update(visible=False),
    )


def exclude_website(pending_exclusion_domain, current_question):
    """Save an explicitly requested exclusion, then recheck the current response."""
    if not pending_exclusion_domain:
        message = "Inspect a citation and select No before excluding a website."
        return refresh_question_after_exclusion(current_question, message)

    matching_excluded_domain = next(
        (
            domain
            for domain in excluded_site_domains
            if normalize_domain(domain) == normalize_domain(pending_exclusion_domain)
        ),
        None,
    )
    if matching_excluded_domain is None:
        excluded_site_domains.append(pending_exclusion_domain)
        save_excluded_site_domains()
        status_message = (
            f"Excluded `{pending_exclusion_domain}` from future responses. This is "
            "your preference, not proof that the website is factually unreliable."
        )
    else:
        status_message = f"`{matching_excluded_domain}` is already excluded."

    return refresh_question_after_exclusion(current_question, status_message)


def restore_selected_website(selected_domain):
    """Restore one website selected from the excluded-domain list."""
    if not selected_domain:
        return (
            format_excluded_sites(),
            gr.update(choices=excluded_site_domains, value=None),
            "Select an excluded website to restore.",
            gr.update(visible=False),
        )

    matching_excluded_domain = next(
        (
            domain
            for domain in excluded_site_domains
            if normalize_domain(domain) == normalize_domain(selected_domain)
        ),
        None,
    )
    if matching_excluded_domain is None:
        return (
            format_excluded_sites(),
            gr.update(choices=excluded_site_domains, value=None),
            "That website is no longer in the excluded list.",
            gr.update(visible=False),
        )

    excluded_site_domains.remove(matching_excluded_domain)
    save_excluded_site_domains()
    return (
        format_excluded_sites(),
        gr.update(choices=excluded_site_domains, value=None),
        f"Restored `{matching_excluded_domain}`. It can be considered for future responses.",
        gr.update(visible=False),
    )


def request_restore_all_confirmation():
    """Ask for confirmation before restoring every excluded website."""
    if not excluded_site_domains:
        return gr.update(visible=False), "There are no excluded websites to restore."
    return gr.update(visible=True), ""


def cancel_restore_all():
    """Close the restore-all confirmation without changing any exclusions."""
    return gr.update(visible=False), ""


def restore_all_websites():
    """Restore all excluded websites after the user confirms the action."""
    if not excluded_site_domains:
        status_message = "There are no excluded websites to restore."
    else:
        excluded_site_domains.clear()
        save_excluded_site_domains()
        status_message = "All excluded websites have been restored."

    return (
        format_excluded_sites(),
        gr.update(choices=excluded_site_domains, value=None),
        status_message,
        gr.update(visible=False),
    )


# Create the page layout and add the project introduction.
with gr.Blocks(title="AI Citation Verification Prototype") as demo:
    gr.Markdown("# AI Citation Verification Prototype")
    gr.Markdown(
        "Inspect citations and assess whether the evidence supports claims in "
        "AI-generated responses."
    )
    gr.Markdown(
        "**Notice:** Responses in this prototype are simulated and are not "
        "generated by a live AI model."
    )

    # Show the questions currently available in the prepared dataset.
    example_question_list = "\n".join(
        f"- {example['question']}" for example in prepared_examples
    )
    gr.Markdown(f"**Available example questions:**\n\n{example_question_list}")

    # Keep the selected citation private to the current user's Gradio session.
    selected_citation_state = gr.State(value=None)
    feedback_state = gr.State(value={})
    pending_exclusion_domain_state = gr.State(value=None)
    current_question_state = gr.State(value="")

    # Place question entry and its response beside the citation evidence panel.
    with gr.Row():
        with gr.Column(scale=1):
            question_input = gr.Textbox(
                label="Your question",
                placeholder="Type a question...",
                lines=2,
            )
            submit_button = gr.Button("Submit Question", variant="primary")

            # Keep the response area read-only and show its citation alongside it.
            response_output = gr.Textbox(
                label="Simulated AI response",
                lines=8,
                interactive=False,
            )
            citation_output = gr.Markdown()
            inspect_citation_button = gr.Button("Inspect Citation")

        with gr.Column(scale=1):
            with gr.Column(visible=False) as evidence_panel:
                evidence_output = gr.Markdown()
                gr.Markdown(
                    "**Does this citation support the information provided?**\n\n"
                    "Your feedback represents your judgement; it is not an "
                    "automated verification of factual accuracy."
                )
                with gr.Row():
                    yes_feedback_button = gr.Button("Yes")
                    no_feedback_button = gr.Button("No")
                    unsure_feedback_button = gr.Button("Unsure")
                feedback_output = gr.Markdown()
                with gr.Column(visible=False) as exclusion_controls:
                    exclusion_prompt_output = gr.Markdown()
                    with gr.Row():
                        exclude_website_button = gr.Button("Exclude Website")
                        keep_website_button = gr.Button("Keep Website")
                hide_evidence_button = gr.Button("Hide Evidence")

    # Let users manage their locally saved website exclusions.
    gr.Markdown("## Excluded Websites")
    gr.Markdown(
        "Exclusion is a user preference, not proof that a website is factually "
        "unreliable."
    )
    excluded_sites_output = gr.Markdown(format_excluded_sites())
    with gr.Row():
        restore_site_dropdown = gr.Dropdown(
            choices=excluded_site_domains,
            label="Website to restore",
            value=None,
        )
        restore_selected_button = gr.Button("Restore Selected Website")
        restore_all_button = gr.Button("Restore All Websites")
    website_action_status = gr.Markdown()
    with gr.Column(visible=False) as restore_all_confirmation_panel:
        gr.Markdown(
            "Are you sure you want to restore all excluded websites? "
            "They may then be considered for future responses."
        )
        with gr.Row():
            confirm_restore_all_button = gr.Button("Confirm Restore All")
            cancel_restore_all_button = gr.Button("Cancel")

    # The button and Enter key use the same function and clear stale evidence.
    question_outputs = [
        response_output,
        citation_output,
        selected_citation_state,
        evidence_output,
        feedback_output,
        evidence_panel,
        exclusion_prompt_output,
        exclusion_controls,
        pending_exclusion_domain_state,
        current_question_state,
        website_action_status,
    ]
    submit_button.click(
        fn=process_question,
        inputs=question_input,
        outputs=question_outputs,
    )
    question_input.submit(
        fn=process_question,
        inputs=question_input,
        outputs=question_outputs,
    )

    # Inspect the current citation or hide its evidence without losing the selection.
    inspect_citation_button.click(
        fn=inspect_citation,
        inputs=[selected_citation_state, feedback_state],
        outputs=[evidence_output, feedback_output, evidence_panel],
    )
    yes_feedback_button.click(
        fn=record_yes_feedback,
        inputs=[selected_citation_state, feedback_state],
        outputs=[
            feedback_output,
            feedback_state,
            exclusion_prompt_output,
            exclusion_controls,
            pending_exclusion_domain_state,
            website_action_status,
        ],
    )
    no_feedback_button.click(
        fn=record_no_feedback,
        inputs=[selected_citation_state, feedback_state],
        outputs=[
            feedback_output,
            feedback_state,
            exclusion_prompt_output,
            exclusion_controls,
            pending_exclusion_domain_state,
            website_action_status,
        ],
    )
    unsure_feedback_button.click(
        fn=record_unsure_feedback,
        inputs=[selected_citation_state, feedback_state],
        outputs=[
            feedback_output,
            feedback_state,
            exclusion_prompt_output,
            exclusion_controls,
            pending_exclusion_domain_state,
            website_action_status,
        ],
    )
    hide_evidence_button.click(
        fn=hide_evidence_preview,
        outputs=[evidence_output, evidence_panel],
    )
    exclude_website_button.click(
        fn=exclude_website,
        inputs=[pending_exclusion_domain_state, current_question_state],
        outputs=question_outputs
        + [
            excluded_sites_output,
            restore_site_dropdown,
            restore_all_confirmation_panel,
        ],
    )
    keep_website_button.click(
        fn=keep_website,
        inputs=pending_exclusion_domain_state,
        outputs=[
            exclusion_controls,
            pending_exclusion_domain_state,
            website_action_status,
        ],
    )
    restore_selected_button.click(
        fn=restore_selected_website,
        inputs=restore_site_dropdown,
        outputs=[
            excluded_sites_output,
            restore_site_dropdown,
            website_action_status,
            restore_all_confirmation_panel,
        ],
    )
    restore_all_button.click(
        fn=request_restore_all_confirmation,
        outputs=[restore_all_confirmation_panel, website_action_status],
    )
    confirm_restore_all_button.click(
        fn=restore_all_websites,
        outputs=[
            excluded_sites_output,
            restore_site_dropdown,
            website_action_status,
            restore_all_confirmation_panel,
        ],
    )
    cancel_restore_all_button.click(
        fn=cancel_restore_all,
        outputs=[restore_all_confirmation_panel, website_action_status],
    )


# Launch the interface when this file is run directly.
if __name__ == "__main__":
    demo.launch()