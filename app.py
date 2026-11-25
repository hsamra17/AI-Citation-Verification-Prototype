import json
from pathlib import Path
from urllib.parse import urlparse

import gradio as gr


# Keep both JSON paths beside this Python file so the app works from any folder.
responses_file_path = Path(__file__).parent / "responses.json"


excluded_sites_file_path = Path(__file__).parent / "excluded_sites.json"


def normalize_domain(domain):
    """Compare website domains without being affected by letter case or a final dot."""
    return domain.strip().rstrip(".").casefold()


def load_prepared_examples():
    """Load and check the response dataset without stopping the interface on errors."""
    try:
        with responses_file_path.open(encoding="utf-8") as responses_file:
            response_dataset = json.load(responses_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [], f"Could not load responses.json: {error}"

    if not isinstance(response_dataset, dict):
        return [], "responses.json must contain an object with an examples list."

    examples = response_dataset.get("examples")
    if not isinstance(examples, list):
        return [], "responses.json must contain an examples list."

    for example_number, example in enumerate(examples, start=1):
        if (
            not isinstance(example, dict)
            or not isinstance(example.get("question"), str)
            or not example["question"].strip()
            or not isinstance(example.get("simulated_answer"), str)
            or not example["simulated_answer"].strip()
            or not isinstance(example.get("citations"), list)
        ):
            return [], f"responses.json example {example_number} has invalid fields."

        for citation in example["citations"]:
            citation_fields = (
                "citation_id",
                "source_title",
                "website_domain",
                "source_url",
                "evidence_preview",
            )
            if not isinstance(citation, dict) or any(
                not isinstance(citation.get(field), str)
                or not citation[field].strip()
                for field in citation_fields
            ):
                return [], f"responses.json example {example_number} has an invalid citation."

            try:
                parsed_source_url = urlparse(citation["source_url"])
            except ValueError:
                return (
                    [],
                    f"responses.json example {example_number} has an invalid source URL.",
                )
            source_hostname = parsed_source_url.hostname
            website_domain = normalize_domain(citation["website_domain"])
            normalized_source_hostname = (
                normalize_domain(source_hostname) if source_hostname else ""
            )
            if (
                parsed_source_url.scheme.casefold() != "https"
                or not normalized_source_hostname
                or (
                    normalized_source_hostname != website_domain
                    and not normalized_source_hostname.endswith(
                        "." + website_domain
                    )
                )
            ):
                return (
                    [],
                    f"responses.json example {example_number} has an invalid source URL.",
                )

    return examples, ""


def load_excluded_site_domains():
    """Create the exclusions file if missing, then safely load its domain list."""
    try:
        # Exclusive creation avoids replacing a file another process created meanwhile.
        try:
            with excluded_sites_file_path.open("x", encoding="utf-8") as new_file:
                new_file.write("[]\n")
        except FileExistsError:
            pass

        with excluded_sites_file_path.open(encoding="utf-8") as excluded_sites_file:
            saved_domains = json.load(excluded_sites_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [], f"Could not load excluded_sites.json: {error}"

    if not isinstance(saved_domains, list):
        return [], "excluded_sites.json must contain a JSON list of website domains."

    loaded_domains = []
    for saved_domain in saved_domains:
        if not isinstance(saved_domain, str) or not normalize_domain(saved_domain):
            return [], "Each excluded website domain must be a non-empty string."

        cleaned_domain = saved_domain.strip().rstrip(".")
        if not any(
            normalize_domain(existing_domain) == normalize_domain(cleaned_domain)
            for existing_domain in loaded_domains
        ):
            loaded_domains.append(cleaned_domain)

    return loaded_domains, ""


prepared_examples, responses_load_error = load_prepared_examples()
excluded_site_domains, excluded_sites_load_error = load_excluded_site_domains()

feedback_messages = {
    "Yes": "Feedback recorded: You believe this citation supports the response.",
    "No": "Feedback recorded: You believe this citation does not support the response.",
    "Unsure": "Feedback recorded: You are unsure whether this citation supports the response.",
}


def normalize_question_text(question):
    """Make questions comparable despite letter case, spacing, or trailing question marks."""
    return " ".join(question.split()).casefold().rstrip(" ?")


def format_feedback_message(feedback_choice):
    """Make the saved feedback choice easy to identify in the interface."""
    return (
        f"**Selected feedback: {feedback_choice}**\n\n"
        f"{feedback_messages[feedback_choice]}"
    )


def is_valid_selected_citation(selected_citation, current_question=None):
    """Confirm state refers to a real, eligible citation for the current question."""
    if (
        responses_load_error
        or excluded_sites_load_error
        or not isinstance(selected_citation, dict)
    ):
        return False

    website_domain = selected_citation.get("website_domain")
    if not isinstance(website_domain, str):
        return False
    if normalize_domain(website_domain) in {
        normalize_domain(domain) for domain in excluded_site_domains
    }:
        return False

    for example in prepared_examples:
        if current_question is not None and normalize_question_text(
            example["question"]
        ) != normalize_question_text(current_question):
            continue
        if selected_citation in example["citations"]:
            return True

    return False


def normalize_domain(domain):
    """Compare website domains without being affected by letter case or a final dot."""
    return domain.strip().rstrip(".").casefold()


def save_excluded_site_domains(domains_to_save):
    """Write changes separately before replacing the saved preference file."""
    temporary_file_path = excluded_sites_file_path.with_name(
        excluded_sites_file_path.name + ".tmp"
    )
    temporary_file_path.write_text(
        json.dumps(domains_to_save, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_file_path.replace(excluded_sites_file_path)


def format_excluded_sites():
    """Build the text shown in the website management section."""
    if excluded_sites_load_error:
        return f"Saved exclusions are unavailable: {excluded_sites_load_error}"
    if not excluded_site_domains:
        return "No websites are currently excluded."

    excluded_domain_list = "\n".join(
        f"- `{domain}`" for domain in excluded_site_domains
    )
    legacy_test_domains = [
        domain
        for domain in excluded_site_domains
        if normalize_domain(domain).endswith(".test")
    ]
    legacy_notice = ""
    if legacy_test_domains:
        legacy_notice = (
            "\n\n**Legacy exclusions:** These `.test` domains belonged to the "
            "earlier illustrative sources and do not match the current sources. "
            "Select one above and click **Restore Selected Website** to remove "
            "its saved exclusion."
        )
    return (
        f"Currently excluded domains:\n\n{excluded_domain_list}{legacy_notice}"
    )


def can_restore_websites():
    """Only enable restoration controls when saved exclusions are readable and present."""
    return bool(excluded_site_domains) and not excluded_sites_load_error


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

    if responses_load_error:
        return reset_question_outputs(
            f"Prepared responses are unavailable: {responses_load_error}",
            question,
        )

    normalized_user_question = normalize_question_text(question)
    excluded_domains = {
        normalize_domain(domain) for domain in excluded_site_domains
    }

    for example in prepared_examples:
        normalized_prepared_question = normalize_question_text(example["question"])
        if normalized_user_question == normalized_prepared_question:
            if excluded_sites_load_error:
                return reset_question_outputs(
                    "A response cannot be selected because saved website exclusions "
                    f"could not be loaded: {excluded_sites_load_error}",
                    question,
                )

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
                "**Genuine source for this simulated response:** "
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
        "This prototype only supports its prepared example questions. Please try "
        "one of the three questions listed above.",
        question,
    )


def inspect_citation(selected_citation, feedback_records, current_question):
    """Show citation evidence and any feedback already recorded for it."""
    if not is_valid_selected_citation(selected_citation, current_question):
        return "", "", gr.update(visible=False)

    evidence_details = (
        "### Prepared source summary\n\n"
        "**Prepared summary of a genuine source; this is not a direct quotation.**\n\n"
        f"**Source title:** {selected_citation['source_title']}\n\n"
        f"**Website domain:** `{selected_citation['website_domain']}`\n\n"
        f"**Prepared evidence summary:** {selected_citation['evidence_preview']}\n\n"
        f"[View Original Source]({selected_citation['source_url']})"
    )
    citation_id = selected_citation["citation_id"]
    previous_choice = (feedback_records or {}).get(citation_id)
    previous_feedback_message = (
        format_feedback_message(previous_choice)
        if previous_choice in feedback_messages
        else ""
    )
    return evidence_details, previous_feedback_message, gr.update(visible=True)


def save_feedback(
    feedback_choice,
    selected_citation,
    feedback_records,
    current_question,
):
    """Save feedback by citation ID and show exclusion controls only after No."""
    if not is_valid_selected_citation(selected_citation, current_question):
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
            format_feedback_message(feedback_choice),
            updated_feedback_records,
            exclusion_prompt,
            gr.update(visible=True),
            website_domain,
            "",
        )

    return (
        format_feedback_message(feedback_choice),
        updated_feedback_records,
        "",
        gr.update(visible=False),
        None,
        "",
    )


def record_yes_feedback(selected_citation, feedback_records, current_question):
    return save_feedback("Yes", selected_citation, feedback_records, current_question)


def record_no_feedback(selected_citation, feedback_records, current_question):
    return save_feedback("No", selected_citation, feedback_records, current_question)


def record_unsure_feedback(selected_citation, feedback_records, current_question):
    return save_feedback(
        "Unsure",
        selected_citation,
        feedback_records,
        current_question,
    )


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
        gr.update(
            choices=excluded_site_domains,
            value=None,
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        gr.update(visible=False),
    )


def exclude_website(
    pending_exclusion_domain,
    current_question,
    selected_citation,
):
    """Save an explicitly requested exclusion, then recheck the current response."""
    if excluded_sites_load_error:
        message = (
            "The website preference file could not be read, so no exclusion was "
            "saved. Fix excluded_sites.json before trying again."
        )
        return refresh_question_after_exclusion(current_question, message)

    if (
        not pending_exclusion_domain
        or not is_valid_selected_citation(selected_citation, current_question)
        or normalize_domain(pending_exclusion_domain)
        != normalize_domain(selected_citation["website_domain"])
    ):
        message = (
            "The selected citation is no longer current. Submit the question and "
            "inspect its citation again before excluding a website."
        )
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
        updated_domains = excluded_site_domains + [pending_exclusion_domain]
        try:
            save_excluded_site_domains(updated_domains)
        except (OSError, UnicodeError) as error:
            status_message = (
                f"Could not save the exclusion: {error}. The website was not "
                "excluded."
            )
            return refresh_question_after_exclusion(current_question, status_message)

        excluded_site_domains[:] = updated_domains
        status_message = (
            f"Excluded `{pending_exclusion_domain}` from future responses. This is "
            "your preference, not proof that the website is factually unreliable."
        )
    else:
        status_message = f"`{matching_excluded_domain}` is already excluded."

    return refresh_question_after_exclusion(current_question, status_message)


def restore_selected_website(selected_domain):
    """Restore one website selected from the excluded-domain list."""
    if excluded_sites_load_error:
        return (
            format_excluded_sites(),
            gr.update(
                choices=excluded_site_domains,
                value=selected_domain,
                interactive=False,
                visible=False,
            ),
            "The saved exclusions could not be read, so no website was restored.",
            gr.update(visible=False),
            gr.update(interactive=False, visible=False),
            gr.update(interactive=False, visible=False),
        )

    if not selected_domain:
        return (
            format_excluded_sites(),
            gr.update(
                choices=excluded_site_domains,
                value=None,
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            "Select an excluded website to restore.",
            gr.update(visible=False),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
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
            gr.update(
                choices=excluded_site_domains,
                value=None,
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            "That website is no longer in the excluded list.",
            gr.update(visible=False),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
        )

    updated_domains = [
        domain
        for domain in excluded_site_domains
        if normalize_domain(domain) != normalize_domain(matching_excluded_domain)
    ]
    try:
        save_excluded_site_domains(updated_domains)
    except (OSError, UnicodeError) as error:
        return (
            format_excluded_sites(),
            gr.update(
                choices=excluded_site_domains,
                value=selected_domain,
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            f"Could not save the restoration: {error}. The website remains excluded.",
            gr.update(visible=False),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
            gr.update(
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            ),
        )

    excluded_site_domains[:] = updated_domains
    return (
        format_excluded_sites(),
        gr.update(
            choices=excluded_site_domains,
            value=None,
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        f"Restored `{matching_excluded_domain}`. It can be considered for future responses.",
        gr.update(visible=False),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
    )


def request_restore_all_confirmation():
    """Ask for confirmation before restoring every excluded website."""
    if excluded_sites_load_error:
        return (
            gr.update(visible=False),
            "Saved website exclusions could not be read, so they cannot be restored.",
        )
    if not excluded_site_domains:
        return gr.update(visible=False), "There are no excluded websites to restore."
    return gr.update(visible=True), ""


def cancel_restore_all():
    """Close the restore-all confirmation without changing any exclusions."""
    return gr.update(visible=False), ""


def restore_all_websites():
    """Restore all excluded websites after the user confirms the action."""
    if excluded_sites_load_error:
        return (
            format_excluded_sites(),
            gr.update(
                choices=excluded_site_domains,
                value=None,
                interactive=False,
                visible=False,
            ),
            "Saved website exclusions could not be read, so they were not restored.",
            gr.update(visible=False),
            gr.update(interactive=False, visible=False),
            gr.update(interactive=False, visible=False),
        )

    if not excluded_site_domains:
        status_message = "There are no excluded websites to restore."
    else:
        try:
            save_excluded_site_domains([])
        except (OSError, UnicodeError) as error:
            return (
                format_excluded_sites(),
                gr.update(
                    choices=excluded_site_domains,
                    value=None,
                    interactive=can_restore_websites(),
                    visible=can_restore_websites(),
                ),
                f"Could not save the restoration: {error}. No websites were restored.",
                gr.update(visible=False),
                gr.update(
                    interactive=can_restore_websites(),
                    visible=can_restore_websites(),
                ),
                gr.update(
                    interactive=can_restore_websites(),
                    visible=can_restore_websites(),
                ),
            )

        excluded_site_domains.clear()
        status_message = "All excluded websites have been restored."

    return (
        format_excluded_sites(),
        gr.update(
            choices=excluded_site_domains,
            value=None,
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        status_message,
        gr.update(visible=False),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
        gr.update(
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        ),
    )


# Create the page layout and add the project introduction.
with gr.Blocks(title="AI Citation Verification Prototype") as demo:
    gr.Markdown("# AI Citation Verification Prototype")
    gr.Markdown(
        "Inspect citations and assess whether the evidence supports claims in "
        "AI-generated responses."
    )
    gr.Markdown(
        "**Educational examples:** Responses are simulated, may contain "
        "inaccurate claims, and are not factual advice. Citation links point to "
        "genuine sources; evidence previews are prepared summaries, not direct "
        "quotations. This prototype does not use a live AI model, web retrieval, "
        "or automatic fact-checking."
    )
    if responses_load_error:
        gr.Markdown(f"**Dataset loading error:** {responses_load_error}")
    if excluded_sites_load_error:
        gr.Markdown(
            "**Website preference loading error:** "
            f"{excluded_sites_load_error} Prepared responses are paused until this "
            "file can be read, so saved exclusions are not ignored."
        )

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
                placeholder="Type a question or choose an example below...",
                lines=2,
            )
            submit_button = gr.Button(
                "Submit Question",
                variant="primary",
                size="md",
            )
            if prepared_examples:
                gr.Examples(
                    examples=[
                        [example["question"]] for example in prepared_examples
                    ],
                    inputs=question_input,
                    label="Click an example question to use it",
                    example_labels=[
                        example["question"] for example in prepared_examples
                    ],
                    examples_per_page=3,
                )
            else:
                gr.Markdown("Prepared example questions are unavailable.")

            # Use a compact response panel to distinguish the simulated answer.
            with gr.Group():
                gr.Markdown("### Simulated AI response")
                response_output = gr.Textbox(
                    label="Prepared response",
                    placeholder="Submit a question to see a prepared response.",
                    lines=4,
                    interactive=False,
                )

        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### Citation inspection")
                gr.Markdown(
                    "Inspect the genuine source and its prepared evidence summary."
                )
                citation_output = gr.Markdown()
                inspect_citation_button = gr.Button(
                    "Inspect Citation",
                    variant="primary",
                    size="md",
                )

            with gr.Group(visible=False) as evidence_panel:
                gr.Markdown("### Genuine source evidence")
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
                        exclude_website_button = gr.Button(
                            "Exclude Website",
                            interactive=not responses_load_error
                            and not excluded_sites_load_error,
                        )
                        keep_website_button = gr.Button("Keep Website")
                hide_evidence_button = gr.Button("Hide Evidence")

    # Let users manage their locally saved website exclusions.
    with gr.Group():
        gr.Markdown("### Excluded Websites")
        gr.Markdown(
            "Manage saved website preferences here. Exclusion is not proof that a "
            "website is factually unreliable."
        )
        excluded_sites_output = gr.Markdown(format_excluded_sites())
        restore_site_dropdown = gr.Dropdown(
            choices=excluded_site_domains,
            label="Select a website to restore",
            value=None,
            interactive=can_restore_websites(),
            visible=can_restore_websites(),
        )
        with gr.Row():
            restore_selected_button = gr.Button(
                "Restore Selected Website",
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            )
            restore_all_button = gr.Button(
                "Restore All Websites",
                interactive=can_restore_websites(),
                visible=can_restore_websites(),
            )
        with gr.Column(visible=False) as restore_all_confirmation_panel:
            gr.Markdown(
                "Are you sure you want to restore all excluded websites? "
                "They may then be considered for future responses."
            )
            with gr.Row():
                confirm_restore_all_button = gr.Button("Confirm Restore All")
                cancel_restore_all_button = gr.Button("Cancel")
        website_action_status = gr.Markdown()

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
        inputs=[selected_citation_state, feedback_state, current_question_state],
        outputs=[evidence_output, feedback_output, evidence_panel],
    )
    yes_feedback_button.click(
        fn=record_yes_feedback,
        inputs=[selected_citation_state, feedback_state, current_question_state],
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
        inputs=[selected_citation_state, feedback_state, current_question_state],
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
        inputs=[selected_citation_state, feedback_state, current_question_state],
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
        inputs=[
            pending_exclusion_domain_state,
            current_question_state,
            selected_citation_state,
        ],
        outputs=question_outputs
        + [
            excluded_sites_output,
            restore_site_dropdown,
            restore_selected_button,
            restore_all_button,
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
            restore_selected_button,
            restore_all_button,
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
            restore_selected_button,
            restore_all_button,
        ],
    )
    cancel_restore_all_button.click(
        fn=cancel_restore_all,
        outputs=[restore_all_confirmation_panel, website_action_status],
    )


# Launch the interface when this file is run directly.
if __name__ == "__main__":
    demo.launch()