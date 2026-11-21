# Classification tree

Code checks the sender first, with the allowlist plus DMARC. The result picks one of the
two trees below.

Rounded boxes are LLM calls. The mapper is plain code. Green boxes are labels. The orange
box is `UNCLASSIFIED`, the escape hatch.

## External sender

```mermaid
flowchart TD
    A[Sender: EXTERNAL] --> EL([LLM: get label<br/>external set])

    %% Longer ---> arrows keep every label on one row
    EL --> E_MKT[MARKETING]:::tag
    EL --> E_SO[SALES_OUTREACH]:::tag
    EL --> E_INF[INFO_ONLY]:::tag
    EL --> E_SPM[SPAM]:::tag
    EL --> E_MTG[MEETING_REQUEST]:::tag
    EL --> E_TSK[TASK]:::tag
    EL --> E_UNC[UNCLASSIFIED]:::unclassified

    E_MTG --> ET([LLM: extract proposed times])
    E_TSK --> EU([LLM: extract urgent])

    subgraph MAP[" "]
        X_MKT[Archive]
        X_SO[Send polite decline,<br/>then archive]
        X_INF[Archive under<br/>Finance label]
        X_SPM[Move to Spam, log]
        X_MTG[Approval by email,<br/>then create calendar event<br/>around existing events]
        X_FLAG[Approval by email,<br/>then flag and notify manager<br/>urgent passed as context]
        X_ULOG[Log only]
    end

    E_MKT ---> X_MKT
    E_SO ---> X_SO
    E_INF ---> X_INF
    E_SPM ---> X_SPM
    ET --> X_MTG
    EU --> X_FLAG
    E_UNC ---> X_ULOG

    classDef tag fill:#d3f9d8,stroke:#2b8a3e,color:#1b4332
    classDef unclassified fill:#ffe8cc,stroke:#d9480f,color:#7c2d12
```

| Email | LLM calls | Action |
| --- | --- | --- |
| Newsletter | label | Archive |
| Cold pitch | label | Send polite decline, then archive |
| Phishing link | label | Move to Spam, log |
| Receipt from a supplier | label | Archive under Finance label |
| Meeting invite from a vendor | label, times | Approval, then create event |
| Task from a customer | label, urgent | Approval, then flag and notify manager |
| Email that fits no label | label | Log only |

## Internal sender

```mermaid
flowchart TD
    A[Sender: INTERNAL] --> IL([LLM: get label<br/>internal set])

    %% Longer ---> arrows keep every label on one row
    IL --> I_TSK[TASK]:::tag
    IL --> I_MTG[MEETING_REQUEST]:::tag
    IL --> I_UNC[UNCLASSIFIED]:::unclassified

    I_MTG --> IT([LLM: extract proposed times])
    I_TSK --> IU([LLM: extract urgent])

    subgraph MAP[" "]
        X_MTG[Approval by email,<br/>then create calendar event<br/>around existing events]
        X_FLAG[Approval by email,<br/>then flag and notify manager<br/>urgent passed as context]
        X_LOG[Log only]
    end

    IT --> X_MTG
    IU --> X_FLAG
    I_UNC ---> X_LOG

    classDef tag fill:#d3f9d8,stroke:#2b8a3e,color:#1b4332
    classDef unclassified fill:#ffe8cc,stroke:#d9480f,color:#7c2d12
```

| Email | LLM calls | Action |
| --- | --- | --- |
| CEO: "contract due today" | label, urgent | Approval, then flag and notify manager |
| Colleague proposes Thu 2pm | label, times | Approval, then create event |
| Colleague shares a newsletter | label | Log only |
