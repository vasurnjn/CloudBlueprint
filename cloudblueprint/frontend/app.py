from __future__ import annotations

import io
import json
import os
import zipfile
import streamlit as st

from cloudblueprint.frontend.api_client import (
    APIClient,
    APIClientError,
    APIConnectionError,
    APIHTTPError,
)

# ----------------------------------------------------
# STREAMLIT CONFIGURATION
# ----------------------------------------------------
st.set_page_config(
    page_title="CloudBlueprint Designer",
    page_icon="☁️",
    layout="wide",
)

# Initialize Session State
if "backend_url" not in st.session_state:
    st.session_state.backend_url = os.environ.get("CLOUDBLUEPRINT_BACKEND_URL", "http://localhost:8000")

if "selected_architecture_id" not in st.session_state:
    st.session_state.selected_architecture_id = None

# Initialize Client
client = APIClient(st.session_state.backend_url)

# Helper function to clear select box state if needed
def select_architecture(arch_id: str | None) -> None:
    if st.session_state.get("selected_architecture_id") != arch_id:
        st.session_state.selected_architecture_id = arch_id
        st.session_state.pop("tf_generation_blocked", None)



# Helper function to create ZIP from files list
def create_zip(files: list[dict]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for f in files:
            zip_file.writestr(f["filename"], f["content"])
    return zip_buffer.getvalue()


# Helper function to generate Graphviz DOT representation
def generate_dot_graph(resources: dict, relationships: list) -> str:
    dot_lines = [
        "digraph G {",
        "  rankdir=TB;",
        '  graph [bgcolor="transparent"];',
        "  node [shape=box, style=filled, fontname=Arial, fontsize=10];",
        "  edge [fontname=Arial, fontsize=8, color=gray];"
    ]
    styles = {
        "VPC": 'fillcolor="#E8DAEF", color="#8E44AD"',
        "PUBLIC_SUBNET": 'fillcolor="#D4EFDF", color="#27AE60"',
        "PRIVATE_SUBNET": 'fillcolor="#FCF3CF", color="#F39C12"',
        "SECURITY_GROUP": 'fillcolor="#EAECEE", color="#7F8C8D"',
        "INTERNET_GATEWAY": 'fillcolor="#D6EAF8", color="#2980B9"',
        "EC2_INSTANCE": 'fillcolor="#FADBD8", color="#C0392B"',
        "APPLICATION_LOAD_BALANCER": 'fillcolor="#FDEDEC", color="#E74C3C"',
        "RDS_DATABASE": 'fillcolor="#EAFAF1", color="#2ECC71"',
        "S3_BUCKET": 'fillcolor="#FEF9E7", color="#F4D03F"',
    }
    for r_id, r in resources.items():
        style = styles.get(r["type"], 'fillcolor="#FFFFFF", color="#000000"')
        safe_name = r["name"].replace('"', '\\"')
        dot_lines.append(f'  "{r_id}" [label="{safe_name}\\n({r["type"]})", {style}];')
    for rel in relationships:
        src = rel["source_id"]
        tgt = rel["target_id"]
        rel_type = rel["type"]
        if src in resources and tgt in resources:
            dot_lines.append(f'  "{src}" -> "{tgt}" [label="{rel_type}"];')
    dot_lines.append("}")
    return "\n".join(dot_lines)


# ----------------------------------------------------
# SIDEBAR - CONFIGURATION & ARCHITECTURE SELECTOR
# ----------------------------------------------------
with st.sidebar:
    # A. CloudBlueprint branding
    st.title("☁️ CloudBlueprint")
    st.caption("Infrastructure Architecture Designer")
    st.markdown("---")

    # E. Advanced / Connection Settings
    connected = False
    try:
        health_resp = client.health()
        if health_resp.get("status") == "ok":
            connected = True
    except Exception:
        pass

    with st.expander("⚙️ Connection Settings", expanded=not connected):
        backend_url = st.text_input(
            "Backend Base URL",
            value=st.session_state.backend_url,
            key="backend_url_input",
        )
        if backend_url != st.session_state.backend_url:
            st.session_state.backend_url = backend_url
            client = APIClient(st.session_state.backend_url)
            st.rerun()
        
        if connected:
            st.success("🟢 Connected to Backend")
        else:
            st.error("🔴 Backend Unreachable")

    st.markdown("---")

    if connected:
        # B. Architecture Workspace
        st.subheader("📁 Workspaces")
        try:
            architectures = client.list_architectures()
        except APIClientError as e:
            st.error(f"Failed to fetch architectures: {str(e)}")
            architectures = []

        arch_options = {a["name"]: a["id"] for a in architectures}
        arch_names = list(arch_options.keys())

        selected_id = st.session_state.selected_architecture_id
        selected_index = 0
        if selected_id:
            for idx, a_id in enumerate(arch_options.values()):
                if a_id == selected_id:
                    selected_index = idx + 1
                    break

        selected_name = st.selectbox(
            "Select Architecture",
            options=["-- Select --"] + arch_names,
            index=selected_index,
            label_visibility="collapsed",
        )

        if selected_name == "-- Select --":
            select_architecture(None)
        else:
            select_architecture(arch_options[selected_name])

        # Create/Import Workspace Expander
        with st.expander("➕ Create/Import Workspace", expanded=False):
            st.markdown("#### Create New")
            with st.form("create_architecture_form", clear_on_submit=True):
                new_id = st.text_input("ID (e.g. prod-web)", help="Unique alphanumeric ID")
                new_name = st.text_input("Name (e.g. Production Web Service)")
                submitted = st.form_submit_button("Create", use_container_width=True)
                if submitted:
                    if not new_id.strip() or not new_name.strip():
                        st.error("Both ID and Name are required.")
                    else:
                        try:
                            res = client.create_architecture({
                                "id": new_id.strip(),
                                "name": new_name.strip(),
                                "resources": {},
                                "relationships": []
                            })
                            select_architecture(res["id"])
                            st.toast(f"Workspace '{res['name']}' created!")
                            st.rerun()
                        except APIClientError as e:
                            st.error(str(e))

            st.markdown("---")
            st.markdown("#### Import JSON")
            uploaded_file = st.file_uploader(
                "Upload JSON file",
                type=["json"],
                key="architecture_import_uploader",
                label_visibility="collapsed",
            )
            if uploaded_file is not None:
                try:
                    import_payload = json.load(uploaded_file)
                    if not isinstance(import_payload, dict) or "id" not in import_payload or "name" not in import_payload:
                        st.error("Invalid architecture JSON format.")
                    else:
                        import_payload.setdefault("resources", {})
                        import_payload.setdefault("relationships", [])
                        res = client.create_architecture(import_payload)
                        select_architecture(res["id"])
                        st.toast(f"Workspace '{res['name']}' imported!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {str(e)}")

        st.markdown("---")

        # C. Quick Start / Examples
        st.subheader("🚀 Quick Start Examples")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Load Valid", use_container_width=True):
                try:
                    res = client.load_example("valid")
                    select_architecture(res["id"])
                    st.toast("Valid example loaded!")
                    st.rerun()
                except APIClientError as e:
                    st.error(str(e))
        with col2:
            if st.button("Load Invalid", use_container_width=True):
                try:
                    res = client.load_example("invalid")
                    select_architecture(res["id"])
                    st.toast("Invalid example loaded!")
                    st.rerun()
                except APIClientError as e:
                    st.error(str(e))

        # D. Architecture Summary
        if st.session_state.selected_architecture_id:
            try:
                temp_arch = client.get_architecture(st.session_state.selected_architecture_id)
                r_count = len(temp_arch.get("resources", {}))
                rel_count = len(temp_arch.get("relationships", []))
            except Exception:
                r_count = 0
                rel_count = 0

            st.markdown("---")
            st.subheader("📊 Workspace Summary")
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Resources", r_count)
            col_m2.metric("Relationships", rel_count)
            
            # Validation status
            val_status = "⚪ Diagnostic Pending"
            if "validation_report" in st.session_state and st.session_state.validation_report:
                report = st.session_state.validation_report
                if report.get("architecture_id") == st.session_state.selected_architecture_id:
                    if report.get("is_valid", False):
                        val_status = "🟢 Valid (Ready)"
                    else:
                        val_status = f"🔴 Invalid ({len(report.get('results', []))} issues)"
            st.markdown(f"**Diagnostics Status:**\n`{val_status}`")

        # F. Danger Zone
        if st.session_state.selected_architecture_id:
            st.markdown("---")
            with st.expander("🚨 Danger Zone", expanded=False):
                st.markdown("### Delete Selected Workspace")
                st.caption("This action is permanent and cannot be undone.")
                confirm_delete = st.checkbox("Confirm Delete", key="sidebar_confirm_delete")
                if st.button(
                    "Delete Selected Architecture",
                    disabled=not confirm_delete,
                    use_container_width=True,
                    type="primary",
                    key="sidebar_delete_btn"
                ):
                    try:
                        client.delete_architecture(st.session_state.selected_architecture_id)
                        st.toast("Architecture deleted successfully.")
                        select_architecture(None)
                        st.rerun()
                    except APIClientError as e:
                        st.error(str(e))



# ----------------------------------------------------
# MAIN AREA
# ----------------------------------------------------
if not connected:
    st.warning("⚠️ The Streamlit application requires a connection to the FastAPI backend. Please start the backend service (typically on port 8000) and update the URL in the sidebar.")
    st.info("💡 To start the backend: `python -m uvicorn cloudblueprint.backend.main:app --reload`")
    st.stop()

if not st.session_state.selected_architecture_id:
    st.title("☁️ CloudBlueprint Workspace")
    st.caption("Infrastructure Architecture Designer")
    st.info("👈 Please select or create an architecture in the sidebar, or load one of the preconfigured example architectures to begin.")
    st.stop()

# Fetch architecture details
try:
    arch = client.get_architecture(st.session_state.selected_architecture_id)
except APIClientError as e:
    st.error(f"Failed to load selected architecture: {str(e)}")
    st.stop()

# Display Selected Architecture Info (Workspace)
st.title(f"📁 {arch['name']}")
st.caption(f"Workspace ID: `{arch['id']}` | Created: {arch['created_at']} | Updated: {arch['updated_at']}")

# Tabs for workflow: DESIGN -> CONNECT -> VALIDATE -> GENERATE
tab1, tab2, tab3, tab4 = st.tabs([
    "📐 1. DESIGN (Resources)",
    "🔗 2. CONNECT (Relationships)",
    "🔍 3. VALIDATE (Diagnostics)",
    "🛠️ 4. GENERATE (Terraform)",
])

resources = arch["resources"]
relationships = arch["relationships"]

# ----------------------------------------------------
# TAB 1: DESIGN (Resources)
# ----------------------------------------------------
with tab1:
    st.markdown("### Resource Configuration")
    st.markdown("Define the cloud resources that make up your infrastructure design.")

    
    # Topology diagram
    st.markdown("#### 🗺️ Topology Diagram")
    if not resources:
        st.info("Add resources to view the interactive architecture diagram.")
    else:
        try:
            dot_str = generate_dot_graph(resources, relationships)
            st.graphviz_chart(dot_str)
        except Exception as e:
            st.info("Visual topology chart is not available on this system. You can view the list of resources in the table below.")

    st.markdown("---")
    
    # Existing resources table
    st.markdown("#### 📦 Existing Resources")
    if not resources:
        st.info("No resources defined in this architecture.")
    else:
        resource_list = []
        for r_id, r in resources.items():
            resource_list.append({
                "ID": r["id"],
                "Name": r["name"],
                "Type": r["type"],
                "Properties": json.dumps(r["properties"]),
                "Tags": json.dumps(r["tags"]),
            })
        st.table(resource_list)

    st.markdown("---")

    col_add, col_edit = st.columns([1, 1])

    with col_add:
        st.markdown("### ➕ Add New Resource")
        
        r_type = st.selectbox(
            "Resource Type",
            options=[
                "VPC",
                "PUBLIC_SUBNET",
                "PRIVATE_SUBNET",
                "SECURITY_GROUP",
                "INTERNET_GATEWAY",
                "EC2_INSTANCE",
                "APPLICATION_LOAD_BALANCER",
                "RDS_DATABASE",
                "S3_BUCKET",
            ],
            key="add_res_type",
        )
        
        r_id = st.text_input("Resource ID", placeholder="e.g. vpc_main, ec2_web", key="add_res_id").strip()
        r_name = st.text_input("Resource Name", placeholder="e.g. Primary VPC, Web Application", key="add_res_name").strip()
        
        # Tags input
        r_tags_input = st.text_input("Tags (comma separated Key=Value)", placeholder="Environment=prod,Tier=app", key="add_res_tags")

        # Type-specific properties
        st.markdown("#### Properties")
        props = {}
        valid_props = True

        if r_type == "VPC":
            props["cidr_block"] = st.text_input("CIDR Block", value="10.0.0.0/16")
            
        elif r_type in ("PUBLIC_SUBNET", "PRIVATE_SUBNET"):
            props["cidr_block"] = st.text_input("CIDR Block", value="10.0.1.0/24")
            props["availability_zone"] = st.text_input("Availability Zone", value="us-east-1a")
            
        elif r_type == "SECURITY_GROUP":
            props["description"] = st.text_input("Description", value="Allow HTTP traffic")
            ingress_default = '[\n  {\n    "from_port": 80,\n    "to_port": 80,\n    "protocol": "tcp",\n    "cidr_blocks": ["0.0.0.0/0"],\n    "description": "HTTP"\n  }\n]'
            egress_default = '[\n  {\n    "from_port": 0,\n    "to_port": 0,\n    "protocol": "-1",\n    "cidr_blocks": ["0.0.0.0/0"],\n    "description": "All outbound"\n  }\n]'
            
            ingress_raw = st.text_area("Ingress Rules (JSON list)", value=ingress_default, height=120)
            egress_raw = st.text_area("Egress Rules (JSON list)", value=egress_default, height=120)
            
            try:
                props["ingress_rules"] = json.loads(ingress_raw) if ingress_raw.strip() else []
            except json.JSONDecodeError:
                st.error("❌ Invalid Ingress Rules JSON format.")
                valid_props = False
                
            try:
                props["egress_rules"] = json.loads(egress_raw) if egress_raw.strip() else []
            except json.JSONDecodeError:
                st.error("❌ Invalid Egress Rules JSON format.")
                valid_props = False
                
        elif r_type == "EC2_INSTANCE":
            props["ami"] = st.text_input("AMI ID", value="ami-1234567890abcdef0")
            props["instance_type"] = st.text_input("Instance Type", value="t3.micro")
            props["associate_public_ip_address"] = st.checkbox("Associate Public IP Address", value=False)
            
        elif r_type == "APPLICATION_LOAD_BALANCER":
            props["internet_facing"] = st.checkbox("Internet Facing", value=True)
            props["listener_port"] = st.number_input("Listener Port", value=80, min_value=1, max_value=65535)
            props["target_port"] = st.number_input("Target Port", value=80, min_value=1, max_value=65535)
            props["protocol"] = st.selectbox("Protocol", options=["HTTP", "HTTPS"], index=0)
            
        elif r_type == "RDS_DATABASE":
            props["engine"] = st.selectbox("DB Engine", options=["postgres", "mysql", "mariadb"], index=0)
            props["instance_class"] = st.text_input("Instance Class", value="db.t3.micro")
            props["allocated_storage"] = st.number_input("Allocated Storage (GB)", value=20, min_value=5)
            props["username"] = st.text_input("Admin Username", value="appadmin")
            props["db_name"] = st.text_input("Database Name", value="appdb")
            props["publicly_accessible"] = st.checkbox("Publicly Accessible", value=False)
            
        elif r_type == "S3_BUCKET":
            props["bucket_prefix"] = st.text_input("Bucket Prefix", value="cloudblueprint-assets-")

        if st.button("Add Resource", disabled=not valid_props or not r_id or not r_name, use_container_width=True):
            # Parse tags
            tags = {}
            if r_tags_input.strip():
                for item in r_tags_input.split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        tags[k.strip()] = v.strip()
            
            payload = {
                "id": r_id,
                "name": r_name,
                "type": r_type,
                "properties": props,
                "tags": tags,
            }
            try:
                client.add_resource(arch["id"], payload)
                st.success(f"Resource '{r_name}' added successfully!")
                st.rerun()
            except APIClientError as e:
                st.error(f"Failed to add resource: {str(e)}")

    with col_edit:
        st.markdown("### 📝 Edit / Delete Existing Resource")
        if not resources:
            st.info("Add some resources first to edit or delete them.")
        else:
            resource_choices = {f"{r['name']} ({r_id})": r_id for r_id, r in resources.items()}
            edit_choice_name = st.selectbox("Select Resource to Edit/Delete", options=list(resource_choices.keys()))
            edit_id = resource_choices[edit_choice_name]
            edit_res = resources[edit_id]

            st.markdown(f"**Resource Type:** `{edit_res['type']}`")
            edit_name = st.text_input("Name", value=edit_res["name"], key="edit_name")
            
            # Serialize tags back to key=value list
            tags_str = ", ".join(f"{k}={v}" for k, v in edit_res["tags"].items())
            edit_tags_input = st.text_input("Tags (comma separated Key=Value)", value=tags_str, key="edit_tags")

            # Properties for editing
            st.markdown("#### Edit Properties")
            edit_props = {}
            edit_valid = True
            
            current_props = edit_res.get("properties", {})

            if edit_res["type"] == "VPC":
                edit_props["cidr_block"] = st.text_input("CIDR Block", value=current_props.get("cidr_block", "10.0.0.0/16"), key="edit_vpc_cidr")
                
            elif edit_res["type"] in ("PUBLIC_SUBNET", "PRIVATE_SUBNET"):
                edit_props["cidr_block"] = st.text_input("CIDR Block", value=current_props.get("cidr_block", "10.0.1.0/24"), key="edit_sub_cidr")
                edit_props["availability_zone"] = st.text_input("Availability Zone", value=current_props.get("availability_zone", "us-east-1a"), key="edit_sub_az")
                
            elif edit_res["type"] == "SECURITY_GROUP":
                edit_props["description"] = st.text_input("Description", value=current_props.get("description", ""), key="edit_sg_desc")
                
                ingress_val = json.dumps(current_props.get("ingress_rules", []), indent=2)
                egress_val = json.dumps(current_props.get("egress_rules", []), indent=2)
                
                ingress_raw = st.text_area("Ingress Rules (JSON list)", value=ingress_val, height=120, key="edit_sg_ingress")
                egress_raw = st.text_area("Egress Rules (JSON list)", value=egress_val, height=120, key="edit_sg_egress")
                
                try:
                    edit_props["ingress_rules"] = json.loads(ingress_raw) if ingress_raw.strip() else []
                except json.JSONDecodeError:
                    st.error("❌ Invalid Ingress Rules JSON format.")
                    edit_valid = False
                    
                try:
                    edit_props["egress_rules"] = json.loads(egress_raw) if egress_raw.strip() else []
                except json.JSONDecodeError:
                    st.error("❌ Invalid Egress Rules JSON format.")
                    edit_valid = False
                    
            elif edit_res["type"] == "EC2_INSTANCE":
                edit_props["ami"] = st.text_input("AMI ID", value=current_props.get("ami", ""), key="edit_ec2_ami")
                edit_props["instance_type"] = st.text_input("Instance Type", value=current_props.get("instance_type", "t3.micro"), key="edit_ec2_type")
                edit_props["associate_public_ip_address"] = st.checkbox("Associate Public IP Address", value=current_props.get("associate_public_ip_address", False), key="edit_ec2_pub")
                
            elif edit_res["type"] == "APPLICATION_LOAD_BALANCER":
                edit_props["internet_facing"] = st.checkbox("Internet Facing", value=current_props.get("internet_facing", True), key="edit_alb_face")
                edit_props["listener_port"] = st.number_input("Listener Port", value=current_props.get("listener_port", 80), min_value=1, max_value=65535, key="edit_alb_lport")
                edit_props["target_port"] = st.number_input("Target Port", value=current_props.get("target_port", 80), min_value=1, max_value=65535, key="edit_alb_tport")
                
                proto = current_props.get("protocol", "HTTP")
                edit_props["protocol"] = st.selectbox("Protocol", options=["HTTP", "HTTPS"], index=0 if proto == "HTTP" else 1, key="edit_alb_proto")
                
            elif edit_res["type"] == "RDS_DATABASE":
                engine = current_props.get("engine", "postgres")
                engine_idx = ["postgres", "mysql", "mariadb"].index(engine) if engine in ("postgres", "mysql", "mariadb") else 0
                edit_props["engine"] = st.selectbox("DB Engine", options=["postgres", "mysql", "mariadb"], index=engine_idx, key="edit_rds_eng")
                
                edit_props["instance_class"] = st.text_input("Instance Class", value=current_props.get("instance_class", "db.t3.micro"), key="edit_rds_class")
                edit_props["allocated_storage"] = st.number_input("Allocated Storage (GB)", value=current_props.get("allocated_storage", 20), min_value=5, key="edit_rds_storage")
                edit_props["username"] = st.text_input("Admin Username", value=current_props.get("username", "appadmin"), key="edit_rds_user")
                edit_props["db_name"] = st.text_input("Database Name", value=current_props.get("db_name", "appdb"), key="edit_rds_name")
                edit_props["publicly_accessible"] = st.checkbox("Publicly Accessible", value=current_props.get("publicly_accessible", False), key="edit_rds_pub")
                
            elif edit_res["type"] == "S3_BUCKET":
                edit_props["bucket_prefix"] = st.text_input("Bucket Prefix", value=current_props.get("bucket_prefix", "cloudblueprint-assets-"), key="edit_s3_prefix")

            # Edit & Delete Buttons
            col_u, col_d = st.columns(2)
            with col_u:
                if st.button("Update Resource", disabled=not edit_valid or not edit_name.strip(), use_container_width=True, type="secondary"):
                    edit_tags = {}
                    if edit_tags_input.strip():
                        for item in edit_tags_input.split(","):
                            if "=" in item:
                                k, v = item.split("=", 1)
                                edit_tags[k.strip()] = v.strip()
                                
                    update_payload = {
                        "id": edit_id,
                        "name": edit_name,
                        "type": edit_res["type"],
                        "properties": edit_props,
                        "tags": edit_tags,
                    }
                    try:
                        client.update_resource(arch["id"], edit_id, update_payload)
                        st.success(f"Resource '{edit_id}' updated successfully!")
                        st.rerun()
                    except APIClientError as e:
                        st.error(f"Failed to update resource: {str(e)}")

            with col_d:
                if st.button("Delete Resource", use_container_width=True, type="primary"):
                    try:
                        client.delete_resource(arch["id"], edit_id)
                        st.success(f"Resource '{edit_id}' deleted successfully!")
                        st.rerun()
                    except APIClientError as e:
                        st.error(f"Failed to delete resource: {str(e)}")

# ----------------------------------------------------
# TAB 2: CONNECT (Relationships)
# ----------------------------------------------------
with tab2:
    st.markdown("### Relationship Mapping")
    st.markdown("Establish connections (containment, attachment, targets, etc.) between your resources.")


    # Existing relationships table
    st.markdown("#### 🔗 Existing Relationships")
    if not relationships:
        st.info("No relationships defined in this architecture.")
    else:
        rel_list = []
        for rel in relationships:
            # Add names if available for easier reading
            source_name = resources.get(rel["source_id"], {}).get("name", "")
            target_name = resources.get(rel["target_id"], {}).get("name", "")
            rel_list.append({
                "Source Resource": f"{rel['source_id']} ({source_name})" if source_name else rel['source_id'],
                "Relationship Type": rel["type"],
                "Target Resource": f"{rel['target_id']} ({target_name})" if target_name else rel['target_id'],
            })
        st.table(rel_list)

    st.markdown("---")

    if len(resources) < 2:
        st.warning("⚠️ You need at least 2 resources to create relationships.")
    else:
        col_rel_add, col_rel_del = st.columns(2)

        with col_rel_add:
            st.markdown("### ➕ Add Relationship")
            
            res_choices = {f"{r['name']} ({r_id})": r_id for r_id, r in resources.items()}
            source_name = st.selectbox("Source Resource", options=list(res_choices.keys()), key="add_rel_src")
            source_id = res_choices[source_name]

            rel_type = st.selectbox(
                "Relationship Type",
                options=[
                    "BELONGS_TO",
                    "ATTACHES_TO",
                    "CONNECTS_TO",
                    "USES_SECURITY_GROUP",
                    "ROUTES_TO",
                    "TARGETS",
                    "DEPENDS_ON",
                ],
                key="add_rel_type",
            )

            # Filter target list to exclude source_id
            target_choices = {k: v for k, v in res_choices.items() if v != source_id}
            
            if not target_choices:
                st.error("No valid target resource available.")
            else:
                target_name = st.selectbox("Target Resource", options=list(target_choices.keys()), key="add_rel_tgt")
                target_id = target_choices[target_name]

                if st.button("Add Relationship", use_container_width=True):
                    rel_payload = {
                        "source_id": source_id,
                        "target_id": target_id,
                        "type": rel_type,
                    }
                    try:
                        client.add_relationship(arch["id"], rel_payload)
                        st.success("Relationship added successfully!")
                        st.rerun()
                    except APIClientError as e:
                        st.error(f"Failed to add relationship: {str(e)}")

        with col_rel_del:
            st.markdown("### 🗑️ Delete Relationship")
            if not relationships:
                st.info("No relationships defined to delete.")
            else:
                rel_choices = []
                for idx, rel in enumerate(relationships):
                    src_name = resources.get(rel["source_id"], {}).get("name", rel["source_id"])
                    tgt_name = resources.get(rel["target_id"], {}).get("name", rel["target_id"])
                    label = f"{src_name} --[{rel['type']}]--> {tgt_name}"
                    rel_choices.append((label, idx))
                
                selected_rel_label, selected_rel_idx = st.selectbox(
                    "Select Relationship to Delete",
                    options=rel_choices,
                    format_func=lambda x: x[0],
                )
                
                rel_to_delete = relationships[selected_rel_idx]

                if st.button("Delete Relationship", use_container_width=True, type="primary"):
                    try:
                        client.delete_relationship(arch["id"], rel_to_delete)
                        st.success("Relationship deleted successfully!")
                        st.rerun()
                    except APIClientError as e:
                        st.error(f"Failed to delete relationship: {str(e)}")

# ----------------------------------------------------
# TAB 3: VALIDATE (Diagnostics)
# ----------------------------------------------------
with tab3:
    st.markdown("### Architecture Diagnostics")
    st.markdown("Diagnose architectural issues, networking faults, and security vulnerabilities.")


    if st.button("Run Architecture Validation", use_container_width=True, type="primary"):
        try:
            report = client.validate_architecture(arch["id"])
            st.session_state.validation_report = report
        except APIClientError as e:
            st.error(f"Validation failed: {str(e)}")

    # Display Validation Results
    if "validation_report" in st.session_state and st.session_state.validation_report:
        report = st.session_state.validation_report
        if report.get("architecture_id") == arch["id"]:
            is_valid = report.get("is_valid", False)
            results = report.get("results", [])

            if is_valid:
                st.success("🎉 Architecture is VALID! No blocking errors found.")
            else:
                st.error("❌ Architecture has validation errors that block Terraform generation.")

            if not results:
                st.info("No validation issues found.")
            else:
                for res_item in results:
                    severity = res_item.get("severity", "INFO")
                    rule_id = res_item.get("rule_id", "")
                    rule_name = res_item.get("rule_name", "")
                    resource_id = res_item.get("resource_id")
                    description = res_item.get("description", "")
                    recommendation = res_item.get("recommendation", "")

                    # Color coding based on severity
                    if severity in ("ERROR", "CRITICAL"):
                        color_tag = "🔴"
                    elif severity == "WARNING":
                        color_tag = "🟡"
                    else:
                        color_tag = "🔵"

                    resource_text = f" (Resource: `{resource_id}`)" if resource_id else ""
                    with st.expander(f"{color_tag} **{severity}**: [{rule_id}] {rule_name}{resource_text}"):
                        st.write(description)
                        if recommendation:
                            st.info(f"💡 **Recommendation:** {recommendation}")
        else:
            # Validation report was for a different architecture
            st.session_state.validation_report = None

# ----------------------------------------------------
# TAB 4: GENERATE (Terraform)
# ----------------------------------------------------
with tab4:
    st.markdown("### Terraform Compilation")
    st.markdown("Compile your design into standardized, syntax-valid AWS Terraform HCL files.")

    st.caption("ℹ️ Outbound internet access for resources in private subnets (NAT Gateway) is not currently modeled in this MVP.")
    st.caption("⚠️ The AMI IDs generated are placeholders. Remember to replace them with valid AMI IDs for your AWS region before actual deployment.")
    
    # Show persistent generation blocked error if present in session state
    if "tf_generation_blocked" in st.session_state:
        err = st.session_state.tf_generation_blocked
        if err.get("architecture_id") == arch["id"]:
            st.error(
                "❌ **Terraform generation is blocked.**\n\n"
                "The selected architecture contains validation errors.\n\n"
                "Please resolve the errors in **3. VALIDATE (Diagnostics)** before generating Terraform."
            )
            with st.expander("Show Blocking Errors Details"):
                st.write(err.get("detail", ""))
        else:
            st.session_state.pop("tf_generation_blocked", None)

    # Load Latest Button (Checks if we can retrieve already generated files)
    col_tfa, col_tfb = st.columns(2)
    with col_tfa:
        gen_tf = st.button("Generate Terraform", use_container_width=True, type="primary")
    with col_tfb:
        load_latest = st.button("Load Latest Generated", use_container_width=True)

    tf_record = None

    if gen_tf:
        st.session_state.pop("tf_generation_blocked", None)
        try:
            tf_record = client.generate_terraform(arch["id"])
            st.session_state.tf_record = tf_record
            st.success("Terraform generated successfully!")
            st.rerun()
        except APIHTTPError as e:
            if e.raw_response and "validation_results" in e.raw_response:
                st.session_state.tf_generation_blocked = {
                    "architecture_id": arch["id"],
                    "detail": e.detail,
                    "validation_results": e.raw_response["validation_results"],
                }
                st.session_state.validation_report = {
                    "architecture_id": arch["id"],
                    "is_valid": False,
                    "results": e.raw_response["validation_results"],
                }
                st.rerun()
            else:
                st.error(f"Terraform Generation Blocked:\n{e.detail}")
        except APIClientError as e:
            st.error(f"Terraform generation failed: {str(e)}")

    if load_latest:
        st.session_state.pop("tf_generation_blocked", None)
        try:
            tf_record = client.get_latest_terraform(arch["id"])
            st.session_state.tf_record = tf_record
            st.info("Latest generated Terraform loaded.")
        except APIHTTPError as e:
            if e.status_code == 404:
                st.warning("No Terraform has been generated for this architecture yet.")
            else:
                st.error(str(e))
        except APIClientError as e:
            st.error(str(e))


    # Show generated files if present in session state
    if "tf_record" in st.session_state and st.session_state.tf_record:
        rec = st.session_state.tf_record
        if rec.get("architecture_id") == arch["id"]:
            files = rec.get("files", [])
            if files:
                st.markdown(f"**Generation ID:** `{rec.get('id')}` | **Generated At:** {rec.get('created_at')}")
                
                # Download button for ZIP
                zip_data = create_zip(files)
                st.download_button(
                    label="📥 Download All Files (ZIP)",
                    data=zip_data,
                    file_name=f"cloudblueprint-terraform-{arch['id']}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
                
                # Render files in tabs
                file_tabs = st.tabs([f["filename"] for f in files])
                for f_tab, f in zip(file_tabs, files):
                    with f_tab:
                        # Streamlit code blocks with Terraform highlighting
                        st.code(f["content"], language="hcl")
        else:
            st.session_state.tf_record = None
