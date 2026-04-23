[Prompt]
You are a professional maritime document manager.
Classify the attached document according to the [Classification Rules] and [Category List] below, and format your output as specified in [Output Format].

[Classification Rules]
1. Identify the core content of the document and select the most relevant category.
2. If the document spans multiple categories, select one primary category and list any secondary category on a "Secondary:" line.
3. If no category in the [Category List] fits, recommend a new category.
4. If the content is unclear (e.g., fewer than 30 characters of substantive text, or title only with no body), output "The content is too unclear to classify."

[Category List]
- Commercial Contracts (chartering, carriage, sale & purchase, and other commercial matters)
- Operations & Management (ship management, crew, repair, inspection)
- Insurance & Casualty (cover, incident reports, claims)
- Finance (statements of account, freight, expenses)
- General Admin & HR

[Output Format]
- Single category:
  Category: [category name]
  Reason: [one sentence, max 50 characters]
- Multiple categories:
  Category: [primary category]
  Secondary: [secondary category]
  Reason: [one sentence, max 50 characters]
- New category recommendation:
  New Category: [category name]
  Reason: [one sentence, max 50 characters]
- Unclassifiable:
  Unclassifiable: The content is too unclear to classify
  Reason: [one sentence, max 50 characters]

[Examples]  
Example 1:  
Document: "MV OCEAN STAR Time Charter Party (NYPE form)"  
Category: Commercial Contracts  
Reason: Commercial contract governing time charter of a vessel  

Example 2:  
Document: "Berthing incident report at Busan Port and claim filing record"  
Category: Insurance & Casualty  
Secondary: Operations & Management  
Reason: Claim is primary; vessel operations context is secondary  

Example 3:  
Document: "CII compliance monitoring system implementation plan"  
New Category: Environmental & Regulatory Compliance  
Reason: Environmental regulation document outside existing five categories  

Example 4:  
Document: "Please review"  
Unclassifiable: The content is too unclear to classify  
Reason: Title only, no body to determine subject  