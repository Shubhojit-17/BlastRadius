# DataHub MCP Mutation Tool Argument Shapes

Cheatsheet for DataHub stdio MCP mutation tools (`mcp-server-datahub@latest`):

---

## 1. `add_tags`
- **Arguments**:
  - `entity_urns`: List of target entity URNs (e.g. `["urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_user_orders,PROD)"]`)
  - `tag_urns`: List of tag URNs (e.g. `["urn:li:tag:blastradius_pending_change"]`)

## 2. `remove_tags`
- **Arguments**:
  - `entity_urns`: List of target entity URNs
  - `tag_urns`: List of tag URNs to detach

## 3. `update_description`
- **Arguments**:
  - `entity_urn`: Target entity URN string
  - `description`: Full updated description string

## 4. `add_structured_properties`
- **Arguments**:
  - `entity_urns`: List of target entity URNs
  - `property_values`: List of property dictionaries, e.g.:
    ```json
    [
      {
        "property_urn": "urn:li:structuredProperty:blastradius_risk_level",
        "values": ["HIGH"]
      },
      {
        "property_urn": "urn:li:structuredProperty:blastradius_pr",
        "values": ["#707"]
      }
    ]
    ```
