# HIPAA and Healthcare Considerations

Session recording in healthcare applications that handle **Protected Health Information (PHI)** introduces HIPAA compliance requirements. PHI in session recordings includes patient names, medical record numbers, diagnoses, treatment information, and any other individually identifiable health information displayed or entered in the recorded interface.

### Business Associate Agreement (BAA)

For applications handling PHI, execute a BAA with the session recording vendor **before deploying the SDK**:

| Vendor | BAA availability |
|:-------|:-----------------|
| Sentry | Enterprise plans |
| Datadog | Enterprise plans |
| FullStory | Enterprise plans |
| Self-hosted OpenReplay | Avoids BAA requirement (data does not leave organizational infrastructure); organizational HIPAA policies still govern the deployment |

### Maximum PHI Masking

Mask **all PHI** in session recordings:

- Patient names
- Dates of birth
- Medical record numbers
- Insurance IDs
- Diagnoses
- Lab results
- Prescription information
- All free-text fields where clinicians or patients may enter health information

Apply maximum masking (mask all text, block all media) on healthcare applications. **Do not selectively unmask elements** that may display PHI.

### Replay Access Audit Logging

Implement audit logging for session replay access:

- Track which internal users viewed which session recordings.
- Include timestamp, viewer identity, and session identifier.

HIPAA requires accounting for PHI disclosures. If a session recording incidentally contains PHI despite masking, the audit log provides the evidence trail for breach assessment.

---
[Back to Overview](./OVERVIEW.md)
