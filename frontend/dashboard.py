# streamlit_app.py
import streamlit as st
import json
import os
import pandas as pd
import uuid
import time
import hashlib
import docker
import contextlib
import io

container_pool = {}  # key: code_hash, value: running container name
function_cache = {}  # key: code_hash, value: image_tag

# --- Authentication ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit and username == "admin" and password == "admin123":
            st.session_state.logged_in = True
        elif submit:
            st.error("Invalid credentials")
    st.stop()

# --- Caching by Code Hash ---
def hash_code(code):
    return hashlib.sha256(code.strip().encode()).hexdigest()

# Initialize caches in session state if not exists
if 'docker_cache' not in st.session_state:
    st.session_state.docker_cache = set()
if 'gvisor_cache' not in st.session_state:
    st.session_state.gvisor_cache = set()

# --- Docker Runner ---
def run_function_docker(code_str, input_payload={}):
    os.makedirs("temp", exist_ok=True)
    code_hash = hash_code(code_str)

    # Save handler.py
    with open("temp/handler.py", "w") as f:
        f.write(code_str)

    # Save input.json
    with open("temp/input.json", "w") as f:
        json.dump(input_payload, f)

    dockerfile = """
    FROM python:3.9-slim
    WORKDIR /app
    COPY handler.py handler.py
    COPY input.json input.json
    CMD ["python", "-c", "import json; from handler import handler; print(json.dumps(handler(json.load(open('input.json')))))"]
    """
    with open("temp/Dockerfile", "w") as f:
        f.write(dockerfile)

    client = docker.from_env()
    image_tag = f"user-func-{code_hash[:8]}"
    container_name = f"container_{code_hash[:8]}"

    try:
        # Cleanup: Remove existing container if it exists
        try:
            old_container = client.containers.get(container_name)
            old_container.remove(force=True)
        except:
            pass

        # Check if it's a warm start
        warm = code_hash in st.session_state.docker_cache
        
        # Build image if not already built
        if not warm:
            image, _ = client.images.build(path="temp", tag=image_tag)
            st.session_state.docker_cache.add(code_hash)

        # Create new container
        container = client.containers.run(image_tag, name=container_name, detach=True)
        container_pool[container_name] = container

        # Wait and get logs
        container.wait(timeout=20)
        output = container.logs().decode("utf-8")

        return {"output": output.strip(), "runtime": "docker", "status": "success", "warm": warm}
    except Exception as e:
        return {"output": str(e), "runtime": "docker", "status": "error", "warm": False}

# --- gVisor Simulated Runner ---
def run_function_gvisor(code_str, input_payload):
    code_hash = hash_code(code_str)
    try:
        # Check for warm start using session state
        warm = code_hash in st.session_state.gvisor_cache
        if not warm:
            st.session_state.gvisor_cache.add(code_hash)

        time.sleep(0.5 if warm else 1.5)

        stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            namespace = {}
            exec(code_str, namespace)
            if "handler" not in namespace:
                raise Exception("Function 'handler' not defined.")
            result = namespace["handler"](input_payload)

        printed_output = stdout_buffer.getvalue().strip()
        final_output = printed_output
        if result is not None:
            final_output += ("\n\nReturn Value:\n" + json.dumps(result, indent=2))

        return {
            "output": f"🔒 gVisor simulated output:\n{final_output.strip()}",
            "runtime": "gvisor",
            "status": "success",
            "warm": warm,
            "duration": round(0.5 if warm else 1.5, 3),
        }
    except Exception as e:
        return {
            "output": f"❌ Error:\n\n{str(e)}",
            "runtime": "gvisor",
            "status": "error",
            "warm": False,
            "duration": 1.5
        }

# --- Sidebar ---
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to", ["Run Function", "Metrics Dashboard", "Function Manager"])

# --- Page 1: Run Function ---
if page == "Run Function":
    st.title("🚀 Run a Serverless Function")

    code = st.text_area("Paste your Python function here", height=200, value="""\
def handler(event):
    return {"message": "Hello", "input": event}
""")

    st.markdown("### 📥 Input Payload (JSON)")
    user_input = st.text_area("Input Payload", value='{"key": "value"}')
    runtime = st.selectbox("Choose a runtime", ["docker", "gvisor"])

    if st.button("Run Now"):
        try:
            input_payload = json.loads(user_input)
        except:
            st.error("❌ Invalid JSON input.")
            st.stop()

        with st.spinner("Running..."):
            start = time.time()
            if runtime == "docker":
                result = run_function_docker(code, input_payload)
            else:
                result = run_function_gvisor(code, input_payload)
            result["duration"] = round(time.time() - start, 3)

        if result["status"] == "success":
            st.success("✅ Output:")
            st.code(result["output"])
        else:
            st.error("❌ Error:")
            st.code(result["output"])

        warm = "🔥 Warm" if result["warm"] else "❄ Cold"
        st.info(f"Runtime: {result['runtime']} | Status: {result['status']} | {warm} | Duration: {result['duration']}s")

        # Store metrics
        os.makedirs("metrics", exist_ok=True)
        metrics_path = "metrics/metrics.json"
        
        new_metric = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "runtime": result["runtime"],
            "success": result["status"] == "success",
            "duration": result["duration"],
            "warm": result["warm"]
        }
        
        # Load existing metrics or create new list
        if os.path.exists(metrics_path):
            with open(metrics_path, 'r') as f:
                try:
                    metrics_data = json.load(f)
                except:
                    metrics_data = []
        else:
            metrics_data = []
        
        # Append new metric and save
        metrics_data.append(new_metric)
        with open(metrics_path, 'w') as f:
            json.dump(metrics_data, f, indent=2)

# --- Page 2: Metrics Dashboard ---
elif page == "Metrics Dashboard":
    st.title("📊 Function Metrics")
    metrics_path = "metrics/metrics.json"

    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            try:
                metrics_data = json.load(f)
                df = pd.DataFrame(metrics_data)

                if not df.empty:
                    st.subheader("📄 Full Execution Metrics")
                    st.dataframe(df, use_container_width=True)

                    st.subheader("📈 Execution Time Comparison")
                    chart_data = df.groupby("runtime")["duration"].mean().reset_index()
                    chart_data.columns = ["Runtime", "Avg Duration (s)"]
                    st.bar_chart(data=chart_data, x="Runtime", y="Avg Duration (s)")

                    st.subheader("📊 Success Rate")
                    success_rate = round((df["success"].sum() / len(df)) * 100, 2)
                    st.metric("Success Rate", f"{success_rate}%")

                    st.subheader("🧮 Average Duration (All)")
                    avg_duration = round(df["duration"].mean(), 3)
                    st.metric("Avg Duration", f"{avg_duration}s")

                    st.subheader("🔥 Warm vs Cold Starts")

                    if "warm" in df.columns:
                       warm_counts = df["warm"].value_counts()
                       warm = warm_counts.get(True, 0)
                       cold = warm_counts.get(False, 0)
                       total = warm + cold

                       col1, col2 = st.columns(2)
                       col1.metric("🔥 Warm Starts", f"{warm} ({(warm/total)*100:.1f}%)")
                       col2.metric("❄ Cold Starts", f"{cold} ({(cold/total)*100:.1f}%)")

                    st.bar_chart(pd.DataFrame({
                    "Starts": [warm, cold]
                    }, index=["Warm", "Cold"]))


                    st.subheader("⚙ Runtime Usage Count")
                    st.bar_chart(df["runtime"].value_counts())
                else:
                    st.warning("No metric data yet. Run a function first.")
            except Exception:
                st.error("Could not read metrics file. Ensure it's valid JSON.")
    else:
        st.warning("No metrics file found yet.")



# --- Page 3: Function Manager ---
elif page == "Function Manager":
    st.title("📁 Function Manager")
    FUNC_PATH = "functions/functions.json"

    def load_functions():
        if os.path.exists(FUNC_PATH):
            with open(FUNC_PATH) as f:
                return json.load(f)
        return []

    def save_functions(funcs):
        os.makedirs("functions", exist_ok=True)
        with open(FUNC_PATH, "w") as f:
            json.dump(funcs, f, indent=2)

    functions = load_functions()
    st.subheader("🔍 Saved Functions")
    for func in functions:
        with st.expander(f"🔹 {func['name']}"):
            st.code(func["code"], language="python")
            col1, col2 = st.columns(2)

            if col1.button(f"Run {func['name']}", key=f"run_{func['id']}"):
                payload = {"demo": "test"}
                if func["runtime"] == "docker":
                    result = run_function_docker(func["code"], payload)
                else:
                    result = run_function_gvisor(func["code"], payload)
                result["duration"] = round(time.time() - time.time(), 3)

                if result["status"] == "success":
                    st.success("Output:")
                    st.code(result["output"])
                else:
                    st.error("Error:")
                    st.code(result["output"])

                warm = "🔥 Warm" if result["warm"] else "❄ Cold"
                st.info(f"Runtime: {result['runtime']} | Status: {result['status']} | {warm}")

            if col2.button(f"Delete {func['name']}", key=f"del_{func['id']}"):
                functions = [f for f in functions if f["id"] != func["id"]]
                save_functions(functions)
                st.success("Deleted successfully.")
                st.experimental_rerun()

    st.subheader("➕ Add or Update Function")
    with st.form("func_form"):
        name = st.text_input("Function Name")
        runtime = st.selectbox("Runtime", ["docker", "gvisor"])
        code = st.text_area("Function Code", height=200)
        submit = st.form_submit_button("Save Function")

        if submit:
            if not name or not code:
                st.warning("Name and code are required.")
            else:
                exists = next((f for f in functions if f["name"] == name), None)
                if exists:
                    exists["code"] = code
                    exists["runtime"] = runtime
                else:
                    functions.append({
                        "id": f"func_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "code": code,
                        "runtime": runtime
                    })
                save_functions(functions)
                st.success("Function saved!")
                st.experimental_rerun()