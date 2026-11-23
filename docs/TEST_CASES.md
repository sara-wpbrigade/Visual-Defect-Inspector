# Every Test Case

This file is the factual inventory of the automated tests. It is generated from the test source, so it stays aligned with the repository.

## How to read this

- **Backend**: one function per `test_*` entry. Parametrized functions execute once per parameter set; the repository reports **255 executed tests from 204 functions**.
- **Frontend**: one `it(...)` title per test. `npm test` reports **148 tests** across 16 test files.
- Every backend test mocks the model or uses a dependency override; no test calls Gemini, Torch inference or Whisper.
- Coverage: backend **87%** overall; frontend **93.8% statements / 85.7% branches**.

## Backend test files

| File                         | Purpose                                                            | Test functions |
| ---------------------------- | ------------------------------------------------------------------ | -------------- |
| `test_audio.py`              | Tests for voice note validation and decoding.                      | 11             |
| `test_batch.py`              | Tests for pure batch decision and summary logic.                   | 5              |
| `test_batches_api.py`        | Tests for the /batches API routes.                                 | 2              |
| `test_config.py`             | Tests for settings validation and report-writer selection.         | 8              |
| `test_export_csv.py`         | Tests for CSV defect log export and formula injection defense.     | 3              |
| `test_factory.py`            | Tests for detector and report-writer construction.                 | 4              |
| `test_gemini_writer.py`      | Tests for the Gemini report writer with an injected fake client.   | 6              |
| `test_health.py`             | Tests for the health endpoint.                                     | 1              |
| `test_images.py`             | Tests for upload validation.                                       | 12             |
| `test_inspection_service.py` | Tests for the inspection service with a stubbed detector.          | 4              |
| `test_inspections_api.py`    | API tests for the inspection endpoints with a stubbed detector.    | 43             |
| `test_overlay.py`            | Tests for the annotated overlay and thumbnail rendering.           | 6              |
| `test_patchcore.py`          | Tests for the PatchCore helpers that need no checkpoint.           | 4              |
| `test_pdf_report.py`         | Tests for the PDF report builder.                                  | 14             |
| `test_report_prompt.py`      | Tests for the AI report prompt and its untrusted-transcript block. | 4              |
| `test_report_service.py`     | Tests for report generation, validation, grounding and fallback.   | 17             |
| `test_repository.py`         | Tests for the SQLite inspection repository.                        | 14             |
| `test_rules.py`              | Tests for the inspection rules and persona config.                 | 18             |
| `test_storage.py`            | Tests for the inspection artifact store.                           | 9              |
| `test_template_writer.py`    | Tests for the deterministic, offline report template.              | 5              |
| `test_transcript.py`         | Tests for transcript cleaning and the prompt-injection guard.      | 7              |
| `test_voice_service.py`      | Tests for the voice note service with a stubbed transcriber.       | 7              |

**Total backend test functions: 204.**

## Backend test cases, file by file

### `test_audio.py`

_Tests for voice note validation and decoding._

| Test                                        | Asserts                                                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------ |
| `test_wav_is_decoded_to_16k_mono_floats`    | A WAV is decoded to float samples with the right duration.                           |
| `test_other_sample_rates_are_resampled`     | A 44.1 kHz file still ends up at 16 kHz.                                             |
| `test_browser_recording_format_is_accepted` | WebM with Opus, what MediaRecorder produces, decodes even without a duration header. |
| `test_format_is_read_from_the_bytes`        | The container is recognised from its first bytes, not from any name.                 |
| `test_empty_voice_note_is_rejected`         | Zero bytes are an error.                                                             |
| `test_unsupported_format_is_rejected`       | Text sent as audio is refused before any decoding.                                   |
| `test_corrupt_audio_is_rejected`            | Files that look like audio but cannot be decoded are refused.                        |
| `test_oversized_voice_note_is_rejected`     | Bytes over the limit are refused before decoding.                                    |
| `test_too_long_voice_note_is_rejected`      | Decoding stops as soon as the duration limit is passed.                              |
| `test_silence_is_detected`                  | A decoded but silent recording is flagged as silent.                                 |
| `test_empty_samples_count_as_silent`        | No samples at all is treated as silence.                                             |

### `test_batch.py`

_Tests for pure batch decision and summary logic._

| Test                                               | Asserts                                                          |
| -------------------------------------------------- | ---------------------------------------------------------------- |
| `test_batch_all_pass_is_passed`                    | A batch where all items pass is PASSED.                          |
| `test_batch_defect_exceeding_severity_is_rejected` | A clear defect exceeding min severity rejects the batch.         |
| `test_batch_defect_below_severity_does_not_reject` | A low severity defect when policy requires HIGH does not reject. |
| `test_batch_needs_review_item_causes_needs_review` | Any item needing review flags the entire batch as NEEDS_REVIEW.  |
| `test_summarize_batch_aggregates_counts`           | Batch summary calculates counts and categories accurately.       |

### `test_batches_api.py`

_Tests for the /batches API routes._

| Test                                      | Asserts                                                                   |
| ----------------------------------------- | ------------------------------------------------------------------------- |
| `test_list_batches_and_get_batch`         | Listing batches returns summaries, and getting a batch returns its items. |
| `test_get_batch_unknown_or_malformed_404` | Unknown or malformed batch id returns 404.                                |

### `test_config.py`

_Tests for settings validation and report-writer selection._

| Test                                                | Asserts                                                                     |
| --------------------------------------------------- | --------------------------------------------------------------------------- |
| `test_template_writer_needs_no_gemini_credentials`  | A fresh clone can run the template writer with no key.                      |
| `test_gemini_writer_requires_both_credentials`      | Selecting Gemini without a key and model fails loudly.                      |
| `test_gemini_writer_reports_the_missing_key_only`   | The error names exactly what is absent.                                     |
| `test_gemini_writer_accepts_a_key_and_model`        | Complete Gemini settings are valid.                                         |
| `test_empty_gemini_key_is_rejected`                 | A key that is present but blank is not a key.                               |
| `test_report_defaults_are_explicit`                 | The offline report tuning has stable documented defaults.                   |
| `test_audio_and_whisper_defaults_are_explicit`      | The voice-note tuning has stable documented defaults.                       |
| `test_factory_rejects_inconsistent_gemini_settings` | Bypassed validation still cannot build a Gemini writer without credentials. |

### `test_export_csv.py`

_Tests for CSV defect log export and formula injection defense._

| Test                                        | Asserts                                                               |
| ------------------------------------------- | --------------------------------------------------------------------- |
| `test_export_csv_header_and_injection`      | CSV output has correct headers and defends against formula injection. |
| `test_export_csv_empty_returns_header_only` | Exporting with no matching records returns only the header.           |
| `test_export_csv_filters`                   | CSV export respects batch_id, category, and only_defects filters.     |

### `test_factory.py`

_Tests for detector and report-writer construction._

| Test                                                  | Asserts                                                                      |
| ----------------------------------------------------- | ---------------------------------------------------------------------------- |
| `test_create_detector_uses_the_checkpoint_and_device` | The detector is built from the configured path and device.                   |
| `test_create_transcriber_uses_the_whisper_settings`   | The transcriber is built from the configured model, device and precision.    |
| `test_create_writer_returns_the_offline_template`     | The template choice never touches the Google SDK.                            |
| `test_create_writer_builds_a_gemini_client`           | Gemini settings become a client with the configured timeout in milliseconds. |

### `test_gemini_writer.py`

_Tests for the Gemini report writer with an injected fake client._

| Test                                                           | Asserts                                                            |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `test_request_uses_the_instruction_json_mode_and_draft_schema` | The provider call must constrain the response to our draft schema. |
| `test_photo_is_attached_and_downscaled`                        | The longest side of the photo is capped before it is sent.         |
| `test_photo_is_omitted_when_disabled`                          | Configuration can switch the photo off without breaking the call.  |
| `test_provider_error_becomes_a_writer_error`                   | A provider crash is wrapped so the service can fall back.          |
| `test_missing_response_text_becomes_a_writer_error`            | An empty answer is a writer failure, not an empty draft.           |
| `test_invalid_json_becomes_a_writer_error`                     | Malformed model output never escapes as untrusted data.            |

### `test_health.py`

_Tests for the health endpoint._

| Test                     | Asserts                                         |
| ------------------------ | ----------------------------------------------- |
| `test_health_returns_ok` | The health endpoint answers 200 with status ok. |

### `test_images.py`

_Tests for upload validation._

| Test                                            | Asserts                                                            |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| `test_valid_png_becomes_rgb`                    | A valid PNG is decoded and converted to RGB.                       |
| `test_jpeg_is_accepted`                         | JPEG is the other allowed real format.                             |
| `test_empty_upload_is_rejected`                 | Empty bytes are an error, not an empty image.                      |
| `test_non_image_bytes_are_rejected`             | Plain text is not an image.                                        |
| `test_unsupported_format_is_rejected`           | A real but unsupported format (GIF) is refused.                    |
| `test_corrupt_image_is_rejected`                | A truncated PNG fails to decode.                                   |
| `test_oversized_upload_is_rejected`             | Bytes over the limit are refused before decoding.                  |
| `test_too_many_pixels_are_rejected`             | A small file can still decode to an enormous image.                |
| `test_svg_is_rejected_with_a_specific_message`  | SVG bytes are refused before decoding, with an actionable message. |
| `test_other_real_formats_name_the_format`       | Real but unsupported formats keep the format-specific message.     |
| `test_pdf_is_rejected_as_an_unsupported_format` | PDF bytes are identified and refused as a document, not a photo.   |
| `test_text_file_named_png_is_rejected`          | A .png filename cannot make ordinary text an image.                |

### `test_inspection_service.py`

_Tests for the inspection service with a stubbed detector._

| Test                                              | Asserts                                                       |
| ------------------------------------------------- | ------------------------------------------------------------- |
| `test_good_item_passes_and_is_accepted`           | A low score with nothing flagged passes with no severity.     |
| `test_large_defect_is_high_severity_and_rejected` | A high score with a large flagged area is rejected.           |
| `test_borderline_score_needs_review`              | A score near the cutoff is flagged for re-inspection.         |
| `test_detector_failure_becomes_a_domain_error`    | A model crash is reported as a DetectionError, not swallowed. |

### `test_inspections_api.py`

_API tests for the inspection endpoints with a stubbed detector._

| Test                                                             | Asserts                                                                     |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `test_defect_returns_reject`                                     | A high score with a large flagged area comes back as a reject.              |
| `test_defect_location_is_returned`                               | A two-dimensional mask gives the report a grid cell and a box.              |
| `test_pass_returns_accept`                                       | A clean photo comes back as a pass with an accept action.                   |
| `test_template_report_runs_without_gemini_credentials`           | The template writer needs no Gemini key or model.                           |
| `test_artifacts_are_stored_under_the_inspection_id`              | The photo, overlay and thumbnail are written with fixed names.              |
| `test_response_carries_created_at_batch_and_image_urls`          | A created inspection answers with its id, time, batch and image URLs.       |
| `test_batch_id_is_optional`                                      | A missing batch id is stored and returned as null.                          |
| `test_bad_batch_id_is_rejected`                                  | A batch id outside the pattern is a 422.                                    |
| `test_non_image_upload_is_rejected`                              | Text sent as a photo is a 400, whatever the filename says.                  |
| `test_empty_upload_is_rejected`                                  | Zero bytes are a 400.                                                       |
| `test_oversized_upload_is_rejected`                              | More bytes than the limit are a 413.                                        |
| `test_too_many_pixels_is_rejected`                               | A tiny file that decodes to a large image is a 413.                         |
| `test_missing_image_is_rejected`                                 | FastAPI's own validation answers 422 when the field is absent.              |
| `test_detector_failure_returns_503`                              | A model crash is reported as an unavailable service.                        |
| `test_history_and_detail_match_the_posted_inspection`            | The list and the detail endpoint return what the POST stored.               |
| `test_history_filters_by_batch_id`                               | A batch query returns only that batch's inspections.                        |
| `test_history_pagination`                                        | Limit and offset page through the history.                                  |
| `test_invalid_history_query_is_rejected`                         | Out-of-range limits and a bad batch id are 422.                             |
| `test_image_endpoints_return_images`                             | Each image endpoint answers with the right media type and real bytes.       |
| `test_unknown_or_malformed_detail_is_404`                        | An unknown or malformed id cannot read a record.                            |
| `test_unknown_or_malformed_image_is_404`                         | An unknown, malformed or missing image is a 404.                            |
| `test_record_survives_a_new_repository`                          | The stored record is readable from the same database file again.            |
| `test_database_file_is_created`                                  | The SQLite database is written to the configured path.                      |
| `test_missing_category_is_rejected`                              | The operator must choose a category; omitting it is a 422.                  |
| `test_category_mismatch_is_rejected_without_writing`             | A photo below the cutoff is a 422 and leaves no files or database row.      |
| `test_unknown_category_is_rejected_without_writing`              | An id outside the catalog is an unknown-category 422.                       |
| `test_categories_endpoint_lists_available_categories`            | GET /categories returns the available ids and their defect types.           |
| `test_category_is_stored_and_returned_without_similarity`        | Success stores and returns the category, and no similarity field anywhere.  |
| `test_two_categories_use_different_detectors_and_bands`          | The same score and area get each category's detector and severity bands.    |
| `test_history_filters_by_category`                               | The history category filter returns only that category's rows.              |
| `test_voice_note_is_transcribed_into_the_response`               | A voice note comes back as a cleaned transcript beside the assessment.      |
| `test_silent_voice_note_reports_no_speech`                       | A silent recording is accepted, with no transcript and no model call.       |
| `test_inspection_without_voice_note_never_calls_the_transcriber` | Photo-only inspections do not touch the speech model.                       |
| `test_injection_in_voice_note_cannot_change_the_verdict`         | Spoken instructions are returned as text and leave the facts untouched.     |
| `test_unsupported_audio_is_rejected_before_anything_is_stored`   | A bad voice note is a 400 and leaves no orphaned photo behind.              |
| `test_empty_voice_note_is_rejected`                              | Zero audio bytes are a 400.                                                 |
| `test_oversized_voice_note_is_rejected`                          | More audio bytes than the limit are a 413.                                  |
| `test_too_long_voice_note_is_rejected`                           | A recording over the duration limit is a 413.                               |
| `test_transcriber_failure_returns_503`                           | A speech model crash is reported as an unavailable service.                 |
| `test_recording_without_samples_reports_no_speech`               | A WAV with a header but no audio is accepted and reported as no speech.     |
| `test_blank_voice_note_form_field_is_ignored`                    | A browser form that sends an empty voice_note field means no voice note.    |
| `test_voice_note_is_persisted_with_the_inspection`               | The detail endpoint returns the stored transcript; the summary stays small. |
| `test_transcript_is_passed_to_the_report_writer`                 | A transcribed note reaches the report writer for the AI wording.            |

### `test_overlay.py`

_Tests for the annotated overlay and thumbnail rendering._

| Test                                                            | Asserts                                                              |
| --------------------------------------------------------------- | -------------------------------------------------------------------- |
| `test_overlay_keeps_the_photo_size_and_mode`                    | The overlay is an RGB image of exactly the photo size.               |
| `test_flagged_pixels_are_tinted_and_clean_pixels_are_untouched` | Only the resized mask region changes, and it shifts towards red.     |
| `test_location_draws_a_box_inside_the_image`                    | A box reaching the far edge is clamped, not drawn outside the photo. |
| `test_unusable_masks_return_an_unchanged_copy`                  | An empty or one-dimensional mask leaves every pixel as it was.       |
| `test_thumbnail_fits_inside_the_requested_size`                 | A wide photo shrinks to the size while keeping its aspect ratio.     |
| `test_thumbnail_never_enlarges_a_small_photo`                   | A photo smaller than the thumbnail size stays as it is.              |

### `test_patchcore.py`

_Tests for the PatchCore helpers that need no checkpoint._

| Test                                             | Asserts                                                     |
| ------------------------------------------------ | ----------------------------------------------------------- |
| `test_to_tensor_is_channel_first_and_scaled`     | White pixels become a float CHW tensor in the 0 to 1 range. |
| `test_to_tensor_expands_greyscale_to_rgb`        | A single-channel image is expanded to three channels.       |
| `test_resolve_device_accepts_an_explicit_value`  | A configured device name is used as is.                     |
| `test_resolve_device_auto_returns_a_real_device` | Auto picks MPS, CUDA or CPU, never an invalid value.        |

### `test_pdf_report.py`

_Tests for the PDF report builder._

| Test                                                    | Asserts                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------------- |
| `test_result_is_a_valid_pdf`                            | The output starts with the PDF marker and has at least one page.          |
| `test_defect_report_shows_the_facts`                    | The header, banner and facts grid carry the verified values.              |
| `test_pass_report_says_pass_and_accept`                 | A passing item shows PASS, the accept action and no defect type.          |
| `test_review_report_flags_manual_review`                | A low-confidence result shows the banner and the notice.                  |
| `test_missing_batch_decision_is_marked_unavailable`     | Without a batch decision the report says so instead of leaving a blank.   |
| `test_template_report_says_no_ai_was_used`              | The closing note and the source row describe a template report.           |
| `test_markup_in_text_is_shown_literally`                | Angle brackets and ampersands in model text are printed, not interpreted. |
| `test_unprintable_characters_do_not_break_the_report`   | Characters outside the built-in font are replaced, not fatal.             |
| `test_long_content_wraps_and_every_page_is_numbered`    | Long text flows onto more pages and each page shows its number.           |
| `test_voice_note_transcript_is_included`                | A transcribed operator note appears in the PDF.                           |
| `test_silent_voice_note_is_reported_as_no_speech`       | A silent recording is named instead of leaving an empty section.          |
| `test_missing_images_show_a_notice_instead_of_breaking` | If the stored images are gone the report still builds, with a notice.     |
| `test_both_photos_are_embedded`                         | The original and the annotated photo appear on the first page.            |
| `test_large_photos_are_shrunk_so_the_pdf_stays_small`   | A huge photo does not bloat the file.                                     |

### `test_report_prompt.py`

_Tests for the AI report prompt and its untrusted-transcript block._

| Test                                              | Asserts                                                        |
| ------------------------------------------------- | -------------------------------------------------------------- |
| `test_prompt_embeds_the_preformatted_facts`       | The facts block carries the exact strings the model may reuse. |
| `test_prompt_has_no_transcript_block_when_absent` | No note means no tag and no transcript heading.                |
| `test_prompt_wraps_a_transcript_as_untrusted`     | A note is fenced with the exact tag the instruction describes. |
| `test_instruction_states_the_guardrails`          | The system instruction names the tag and demands JSON only.    |

### `test_report_service.py`

_Tests for report generation, validation, grounding and fallback._

| Test                                                       | Asserts                                                                    |
| ---------------------------------------------------------- | -------------------------------------------------------------------------- |
| `test_ai_writer_returns_validated_content`                 | A grounded draft from the writer is used as the AI report.                 |
| `test_writer_receives_facts_built_from_the_assessment`     | The writer can only word the facts; it cannot supply them.                 |
| `test_ungrounded_number_is_retried_then_falls_back`        | A number that is not in the facts triggers the deterministic template.     |
| `test_invalid_draft_falls_back`                            | An empty findings list breaks the strict schema, so the template is used.  |
| `test_writer_error_falls_back`                             | A provider failure never fails the inspection.                             |
| `test_configured_template_writer_is_reported_as_template`  | The offline writer is labelled as the template source.                     |
| `test_report_source_comes_from_the_writer`                 | The service trusts the writer's declared source.                           |
| `test_template_source_skips_the_retries`                   | A template writer is deterministic, so a failure falls back immediately.   |
| `test_pass_draft_cannot_name_a_defect_type`                | A passing item must have a null defect type.                               |
| `test_unknown_defect_type_is_allowed_and_normalized`       | The literal unknown is allowed when the model cannot name the defect.      |
| `test_unnamed_defect_type_is_allowed`                      | A writer may decline to guess, which keeps the template fallback valid.    |
| `test_unlisted_defect_type_is_rejected`                    | A defect type outside the persona list is a validation error.              |
| `test_needs_review_sets_the_code_owned_notice`             | A borderline assessment gets the manual review notice from code.           |
| `test_number_from_the_transcript_is_allowed`               | Numbers spoken by the operator are available to the writer.                |
| `test_injection_in_the_transcript_cannot_change_the_facts` | The transcript is data, so the assessment still drives verdict and action. |
| `test_blank_transcript_is_treated_as_absent`               | Whitespace-only notes never reach the writer.                              |
| `test_transcript_is_capped_before_it_reaches_the_writer`   | The configured character limit bounds the note.                            |

### `test_repository.py`

_Tests for the SQLite inspection repository._

| Test                                         | Asserts                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| `test_add_then_get_round_trips_equal`        | A stored record comes back with the same facts and report.                |
| `test_unknown_id_returns_none`               | An id that was never stored is absent, not an error.                      |
| `test_malformed_id_is_rejected`              | A malformed id never reaches the database.                                |
| `test_initialize_is_idempotent`              | Creating the schema twice leaves one usable table.                        |
| `test_list_is_newest_first`                  | The history starts with the most recent inspection.                       |
| `test_list_paginates`                        | Limit and offset select one page of the newest-first list.                |
| `test_list_filters_by_batch_id`              | A batch filter returns only that batch, newest first.                     |
| `test_count_totals_and_filters`              | Count reports the total and the per-batch total.                          |
| `test_summary_carries_the_history_fields`    | A listed record exposes the assessment fields, batch id and images.       |
| `test_hostile_values_are_kept_as_plain_data` | A hostile batch id is bound as data and cannot damage the table.          |
| `test_corrupt_row_raises_storage_error`      | A row that is not valid record JSON becomes a domain error.               |
| `test_summary_includes_the_category`         | A history row carries the category that produced it.                      |
| `test_list_filters_by_category`              | A category filter returns only that category's rows.                      |
| `test_version_one_database_is_migrated`      | An older database gains the category column and old rows read as unknown. |

### `test_rules.py`

_Tests for the inspection rules and persona config._

| Test                                                         | Asserts                                                               |
| ------------------------------------------------------------ | --------------------------------------------------------------------- |
| `test_area_ratio_counts_flagged_pixels`                      | A quarter of flagged pixels gives a ratio of 0.25.                    |
| `test_area_ratio_rejects_empty_mask`                         | An empty mask is an error, not a zero.                                |
| `test_decide_verdict`                                        | Scores at or above the cutoff are defects.                            |
| `test_locate_defect_names_the_grid_cell`                     | The centroid of the flagged pixels selects one of the nine cells.     |
| `test_locate_defect_returns_normalized_bbox`                 | The box is the flagged bounds divided by the image size.              |
| `test_locate_defect_returns_none_for_an_empty_mask`          | A two-dimensional mask with no flagged pixel has no location.         |
| `test_locate_defect_returns_none_for_a_one_dimensional_mask` | The flat masks used by the detector contract have no location.        |
| `test_classify_severity`                                     | Band limits are inclusive upper bounds.                               |
| `test_assess_adds_location_for_a_defect`                     | A defect gets the grid cell and box of the flagged pixels.            |
| `test_assess_has_no_location_for_a_pass`                     | A passing item has no defect location, even if pixels were flagged.   |
| `test_assess_clean_item_is_accepted`                         | A low score with nothing flagged passes with no severity.             |
| `test_assess_large_defect_is_rejected`                       | A high score with a large flagged area is high severity and rejected. |
| `test_assess_borderline_score_needs_review`                  | A score near the cutoff is flagged for re-inspection.                 |
| `test_shipped_persona_file_is_valid`                         | The real config file loads and passes validation.                     |
| `test_persona_name_blocks_path_traversal`                    | A name that tries to leave the config folder is rejected.             |
| `test_persona_rejects_unordered_bands`                       | Severity bands must increase.                                         |
| `test_persona_requires_action_text_for_every_action`         | A missing action sentence is a config error.                          |
| `test_persona_rejects_blank_action_text`                     | An empty action sentence is a config error.                           |

### `test_storage.py`

_Tests for the inspection artifact store._

| Test                                             | Asserts                                                          |
| ------------------------------------------------ | ---------------------------------------------------------------- |
| `test_valid_id_is_accepted`                      | A 32-character lowercase hex id passes the check.                |
| `test_new_id_is_always_valid`                    | The random id generator produces ids that pass the check.        |
| `test_unsafe_ids_are_rejected`                   | Ids that could escape the folder never reach a path.             |
| `test_paths_use_fixed_names_derived_from_the_id` | Each kind maps to one fixed file name in the upload folder.      |
| `test_save_writes_the_fixed_file_names`          | Saving each artifact creates exactly the documented file.        |
| `test_unknown_kind_is_rejected`                  | A kind outside the fixed set is a domain error, not a file name. |
| `test_saved_thumbnail_is_a_jpeg`                 | The thumbnail file is written as JPEG bytes.                     |
| `test_id_rejection_is_a_storage_error`           | The specific id error is part of the storage error family.       |
| `test_store_creates_its_directory`               | Saving into a missing folder creates it.                         |

### `test_template_writer.py`

_Tests for the deterministic, offline report template._

| Test                                             | Asserts                                                                  |
| ------------------------------------------------ | ------------------------------------------------------------------------ |
| `test_template_uses_the_persona_action_sentence` | Each action maps to its configured sentence, with no defect guess.       |
| `test_template_declares_its_source`              | The service reads the source from the writer itself.                     |
| `test_template_is_deterministic`                 | The same facts always produce the same draft.                            |
| `test_template_adds_no_numbers_beyond_the_facts` | The template may only repeat the numbers already formatted in the facts. |
| `test_template_names_the_region_for_a_defect`    | A two-dimensional mask gives the summary and findings a grid cell.       |

### `test_transcript.py`

_Tests for transcript cleaning and the prompt-injection guard._

| Test                                                          | Asserts                                                               |
| ------------------------------------------------------------- | --------------------------------------------------------------------- |
| `test_whitespace_and_control_characters_are_normalised`       | Newlines, tabs and runs of spaces become single spaces.               |
| `test_invisible_formatting_characters_are_removed`            | Zero-width characters cannot hide text from a reader.                 |
| `test_long_transcript_is_capped_and_flagged`                  | Text over the limit is cut and marked as truncated.                   |
| `test_angle_brackets_are_removed_so_the_tag_cannot_be_forged` | A transcript cannot close the wrapper tag or open a new one.          |
| `test_fullwidth_brackets_cannot_sneak_past`                   | Look-alike brackets are normalised first, then removed.               |
| `test_wrapped_transcript_stays_inside_exactly_one_tag_pair`   | After cleaning, the only tags in the wrapped block are the real ones. |
| `test_notice_tells_the_model_the_text_is_data`                | The prompt notice names the tag and says not to follow instructions.  |

### `test_voice_service.py`

_Tests for the voice note service with a stubbed transcriber._

| Test                                              | Asserts                                                                    |
| ------------------------------------------------- | -------------------------------------------------------------------------- |
| `test_speech_is_transcribed`                      | Audible audio returns the cleaned transcript and language.                 |
| `test_silent_audio_never_reaches_the_model`       | Silence is answered without loading or running the speech model.           |
| `test_blank_transcription_means_no_speech`        | If the model hears nothing, the result says so.                            |
| `test_long_transcript_is_truncated`               | The transcript cap is applied and reported.                                |
| `test_injection_text_is_kept_as_plain_data`       | Instructions in a voice note are just text, with no brackets left in them. |
| `test_transcriber_failure_becomes_a_domain_error` | A speech model crash is reported, not swallowed.                           |
| `test_model_is_only_loaded_when_needed`           | The provider is not called until a note actually needs transcribing.       |

## Important parametrized backend cases

Some functions run multiple times. These are the parameter sets worth
explaining in the demo:

| Test                                      | Parameter sets                                                                                             |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `test_decide_verdict`                     | score `0.2` → pass; `0.5` and `0.9` → defect                                                               |
| `test_classify_severity`                  | ratio `0.005`/`0.01` → low; `0.03`/`0.05` → medium; `0.2` → high                                           |
| `test_format_is_read_from_the_bytes`      | RIFF/WAVE → wav; OggS → ogg; WebM magic → webm; ftyp → mp4; ID3 and MP3 sync → mp3; AVI/plain/empty → None |
| `test_corrupt_audio_is_rejected`          | bad RIFF, truncated WAV, OggS with junk → invalid audio                                                    |
| `test_bad_batch_id_is_rejected`           | `bad!id` and a 41-character id → 422                                                                       |
| `test_invalid_history_query_is_rejected`  | limit 0, limit 101, negative offset, bad batch id → 422                                                    |
| `test_image_endpoints_return_images`      | photo/overlay → PNG; thumbnail → JPEG                                                                      |
| `test_unknown_or_malformed_detail_is_404` | unknown 32-hex id and `../escape` → 404                                                                    |
| `test_unknown_or_malformed_image_is_404`  | every artifact kind with unknown/malformed id → 404                                                        |
| `test_non_image_upload_is_rejected`       | text, wrong filename, empty bytes → 400                                                                    |
| `test_oversized_upload_is_rejected`       | tiny byte limit → 413                                                                                      |
| `test_too_many_pixels_is_rejected`        | tiny file, large decoded image → 413                                                                       |

## Frontend test files and cases

### `src/App.test.jsx`

_Full app flow with mocked API: tabs, upload, result, errors, shortcuts, theme, batch context, history modal._

| Test                                                                    |
| ----------------------------------------------------------------------- |
| shows the empty state and the upload flow before any inspection         |
| runs a real defect flow from photo selection to verdict                 |
| shows the loading state and disables the inspect action in flight       |
| shows an API error and lets the operator start over                     |
| marks a low-confidence result for manual review                         |
| shows the batch context and refreshes recent inspections after a result |
| switches to batch history and opens a stored inspection                 |
| opens the shortcut reference and handles the keyboard shortcuts         |
| toggles between the light and dark themes                               |
| retries loading categories after a failure                              |
| returns to the inspection tab from the header action                    |

### `src/components/BatchContextStrip.test.jsx`

_Debounced batch lookup, decision labels, new/error states and View batch._

| Test                                             |
| ------------------------------------------------ |
| renders nothing without a valid batch id         |
| loads and shows an existing batch, then opens it |
| says a missing batch is new                      |
| reports a batch that cannot be loaded            |
| shows the Passed decision (`it.each`)            |
| shows the Needs review decision (`it.each`)      |

### `src/components/BatchesHistoryView.test.jsx`

_KPIs, batch table and detail, export/PDF, filters, pagination, empty/error states._

| Test                                                         |
| ------------------------------------------------------------ |
| renders the KPIs, batch table and history rows               |
| loads the first batch detail and filters the history from it |
| selects another batch in the table                           |
| exports a batch CSV                                          |
| downloads a PDF from a history row                           |
| shows empty states when no batches or inspections exist      |
| shows load errors for batches and history                    |
| exports the whole defect log with the active filters         |
| shows an error toast when an export fails                    |
| pages through a longer history                               |
| labels a batch that needs review                             |
| refreshes batches, today count and history                   |

### `src/components/ErrorBoundary.test.jsx`

_Render-error fallback, dismiss and recovery._

| Test                                            |
| ----------------------------------------------- |
| shows the recovery card and dismisses the error |
| renders its children when nothing throws        |

### `src/components/RecentInspections.test.jsx`

_Recent cards, open, View all, empty/error, refresh key._

| Test                                 |
| ------------------------------------ |
| shows recent items and opens one     |
| offers a link to the full history    |
| shows the empty state                |
| shows a load error                   |
| reloads when the refresh key changes |

### `src/components/ResultCard.test.jsx`

_Decision-first result, report, review banner, defect chip, template badge, images, PDF, voice note._

| Test                                                              |
| ----------------------------------------------------------------- |
| shows a pass with its confidence, severity and recommended action |
| shows a high severity defect as a reject                          |
| flags a borderline score as needing manual review                 |
| renders the AI report under the facts                             |
| shows the report manual review notice as a warning banner         |
| hides the defect type chip for a pass without a type              |
| says the defect type is not determined when a defect has none     |
| labels a template report as offline                               |
| shows a voice note conflict only when the report flags one        |
| falls back to raw enum values when the API adds a new one         |
| offers a fresh inspection and forwards the reset                  |
| switches between the overlay and the original photo               |
| downloads the PDF report and shows a failure                      |
| disables the PDF button when no report is available               |
| shows a transcribed voice note                                    |
| shows the batch decision, category and batch id when present      |

### `src/components/ResultModal.test.jsx`

_Loading/error/result modal and close interactions._

| Test                                                    |
| ------------------------------------------------------- |
| shows the loading card while a result is fetched        |
| shows an error with a close button                      |
| renders the stored result and forwards reset            |
| closes on the close button, Escape and a backdrop click |

### `src/components/ShortcutsModal.test.jsx`

_Open/closed, Escape, backdrop, close button._

| Test                                           |
| ---------------------------------------------- |
| renders nothing while closed                   |
| lists the shortcuts and closes from the button |
| closes on Escape and a backdrop click          |

### `src/components/StatusPanels.test.jsx`

_Empty/loading/error states, category mismatch, retry, skeleton._

| Test                                                             |
| ---------------------------------------------------------------- |
| explains what the result will contain                            |
| announces that the inspection is running                         |
| shows the API message and forwards the reset                     |
| has a safe fallback when no error object is passed               |
| explains a category mismatch and offers the supported categories |
| reports the category list loading failure and retries            |
| renders the placeholder grid                                     |

### `src/components/Toast.test.jsx`

_Tone, dismiss and auto-dismiss._

| Test                                                   |
| ------------------------------------------------------ |
| shows the message with its tone and dismisses on click |
| auto-dismisses after the duration                      |

### `src/components/UploadPanel.test.jsx`

_Photo/camera/drop, validation, batch id, category, audio upload/record/remove._

| Test                                                          |
| ------------------------------------------------------------- |
| starts with the inspect action disabled                       |
| accepts a PNG, previews it and sends it for inspection        |
| rejects an unsupported file before calling the API            |
| rejects an empty file and a file over the limit               |
| accepts a photo dropped onto the dropzone                     |
| replaces the preview when a second photo is chosen            |
| highlights the dropzone while a file is dragged over it       |
| opens the picker and the camera from their buttons            |
| disables the actions while an inspection is running           |
| releases the preview object URL when it unmounts              |
| validates the optional batch id before allowing an inspection |
| reports batch id changes to the parent                        |
| forwards the selected category and batch id                   |
| attaches, previews and removes an uploaded voice note         |
| rejects empty, oversized and unsupported audio files          |
| explains when recording is unsupported                        |
| explains a denied microphone permission                       |
| records a voice note and stops at the operator request        |

### `src/hooks/useBackendHealth.test.jsx`

_Health polling, down on failure, interval._

| Test                                                     |
| -------------------------------------------------------- |
| reports ok when the health endpoint answers              |
| reports down for a failed response or a rejected request |
| checks again on the polling interval                     |

### `src/hooks/useInspection.test.jsx`

_Idle/loading/success/error/reset and option forwarding._

| Test                                                   |
| ------------------------------------------------------ |
| starts idle with no result and no error                |
| moves to loading, then success with the inspection     |
| reports loading while the request is in flight         |
| moves to error and returns null when the request fails |
| forwards category, batch and voice-note options        |
| resets back to the idle state                          |

### `src/lib/format.test.js`

_Percent, score, file size and relative time._

| Test                                                      |
| --------------------------------------------------------- |
| formats a ratio with one decimal                          |
| formats the anomaly score with three decimals             |
| uses kilobytes below one megabyte                         |
| uses one decimal of megabytes at or above one megabyte    |
| returns an empty string for missing or unparseable values |
| formats recent and older timestamps                       |
| uses a calendar date for older timestamps                 |

### `src/lib/validateImage.test.js`

_Image type/size/extension validation._

| Test                                                         |
| ------------------------------------------------------------ |
| accepts JPEG and PNG content types                           |
| falls back to the extension when the browser reports no type |
| rejects other image formats                                  |
| asks for a file when nothing is selected                     |
| rejects an empty file                                        |
| rejects an unsupported type                                  |
| rejects a file over the upload limit                         |
| accepts a photo exactly at the limit                         |

### `src/services/api.test.js`

_HTTP contract: POST, categories, batches, history, detail, PDF, CSV, errors, malformed bodies._

| Test                                                        |
| ----------------------------------------------------------- |
| posts the photo to /inspections and normalizes the response |
| keeps a pass without a location and a template report       |
| maps an optional voice note and its transcript              |
| rejects a malformed voice-note block                        |
| shows the server detail when a voice note is unusable       |
| maps a bad image to an operator-friendly message            |
| maps an oversized photo with the same limit the UI shows    |
| maps a missing photo field and an unavailable model         |
| reports a network failure when fetch rejects                |
| falls back to the server detail for an unmapped status      |
| joins FastAPI validation details for an unmapped status     |
| uses the generic message when an error body is not JSON     |
| rejects a success response that does not match the contract |
| rejects a report with an unknown source or missing content  |
| rejects report lists that are empty or not text             |
| rejects a location that is missing or outside the photo     |
| builds ApiError with a safe default status                  |
| maps the category list to camelCase                         |
| falls back for a missing display name and defect list       |
| rejects a non-array body                                    |
| maps network and HTTP failures                              |
| maps batch summaries and sends paging parameters            |
| tolerates a missing category list                           |
| rejects a non-array body and network failures               |
| maps the summary and item rows                              |
| uses empty defaults for a partial summary                   |
| maps HTTP and network failures                              |
| maps history rows and appends filters                       |
| falls back to the item count and omits empty filters        |
| uses empty lists and derived URLs when rows are partial     |
| maps HTTP and network failures                              |
| normalizes one stored inspection                            |
| maps HTTP and network failures                              |
| downloads the PDF and triggers a browser download           |
| maps HTTP and network failures                              |
| downloads a CSV with the selected filters                   |
| uses only_defects by default                                |
| maps HTTP and network failures                              |

**Total frontend test cases: 148** (146 single `it` blocks + 2 `it.each` decision cases).
