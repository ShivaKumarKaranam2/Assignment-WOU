---
name: claims-document-validation
description: Use when checking whether uploaded claim documents are correct, complete, and readable before any policy evaluation begins.
---

# Document Validation Skill

## Purpose

Validate the uploaded claim documents before any policy comparison or decisioning.

## What to Check

- Correct document type for the claim category
- Required document completeness
- Readability and file usability
- Whether the upload is specific enough to continue processing

## Required Behavior

- Stop immediately if the wrong document type is uploaded.
- Stop immediately if required documents are missing.
- Stop immediately if the file is unreadable or unusable.
- Return a specific message that tells the user exactly what is wrong and what to upload instead.
- Do not continue into policy matching if validation fails.

## Output

Return:

- validation status
- missing or wrong documents
- unreadable files
- user-facing correction message

## When to Use

Use this skill only for the first stage of claims processing.
