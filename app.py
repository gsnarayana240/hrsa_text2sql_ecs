import pandas as pd
import snowflake.connector
import os
import json
import re
import sqlparse
from datetime import datetime, timedelta
import requests
import plotly.express as px
import requests
import streamlit as st
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional,get_type_hints
import boto3
import pandas as pd



#url ="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/topicgeneration"
#url="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/testonlymodel"
#inputtopic="Total funding amount given to grant receipients who received their first grant in FY2023 (where FY2023 is their earliest grant award_year in data"

lambda_client = boto3.client('lambda', region_name='us-east-1')
function_name = 'testonlymodel'
payload = {'callwhichfunction': 'generate_sql'}



#SNOWFLAKE_ACCOUNT   = "RRRWUWL-JK62099" #os.getenv("SNOWFLAKE_ACCOUNT")
#SNOWFLAKE_USER      = "SNOWFLAKEPOC"#os.getenv("SNOWFLAKE_USER")
#SNOWFLAKE_PASSWORD  = "testingSnowflake2025" #os.getenv("SNOWFLAKE_PASSWORD")
#SNOWFLAKE_WAREHOUSE = "COMPUTE_WH" #os.getenv("SNOWFLAKE_WAREHOUSE")
#SNOWFLAKE_DATABASE  = "POC" #os.getenv("SNOWFLAKE_DATABASE")
#SNOWFLAKE_SCHEMA    = "PUBLIC" #os.getenv("SNOWFLAKE_SCHEMA")

#SNOWFLAKE_ACCOUNT="RM07780.us-east-2.aws"
#SNOWFLAKE_USER="snowflakepoc"
#SNOWFLAKE_PASSWORD="testingSnowflake2025"
#SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
#SNOWFLAKE_DATABASE="POC"
#SNOWFLAKE_SCHEMA="PUBLIC"




region = os.environ.get("region")
secret_manager=os.environ.get("secret_manager")

def get_secret_dict(client, secret_name):
    secret_string = client.get_secret_value(SecretId=secret_name)
    required_fields = ['SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_PASSWORD', 'SNOWFLAKE_WAREHOUSE', 'SNOWFLAKE_WAREHOUSE', 'SNOWFLAKE_DATABASE', 'SNOWFLAKE_SCHEMA', 'APIGATEWAY_URL']
    secret_dict = json.loads(secret_string['SecretString'])
    for field in required_fields:
        if field not in secret_dict:
            print('Error getting the secret manager field')
            raise
        return secret_dict

secretsmanagerclient = boto3.client('secretsmanager', region_name=region)  # changed to varable name
secretstring = get_secret_dict(secretsmanagerclient, secret_manager)
url=secretstring['APIGATEWAY_URL']

CACHE_FILE = "profiling_cache.json"
CACHE_TTL_HOURS = 24


#def getQuery(inputtopic):
#    try:
#        body = inputtopic
#        response = requests.post(url, json=body)
#        return response
#    except Exception as ex:
#        print(ex)

class GraphState(TypedDict):
    question: str
    sql: Optional[str]
    df: Optional[pd.DataFrame]
    summary: Optional[str]
    error: Optional[str]
    history: list
    context: Optional[str]


#url ="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/topicgeneration"
#url="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/testbedrockwithlanggraph"
#url="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/testonlymodel"
#url="https://6tiwvba334.execute-api.us-east-1.amazonaws.com/development/testanthropiccall"
#inputtopic="Total funding amount given to grant receipients who received their first grant in FY2023 (where FY2023 is their earliest grant award_year in data"

def getQuery(inputtopic):
    try:
        body =inputtopic
        #st.write(json.dumps(inputtopic))        
        response = requests.post(url, json=inputtopic)
        #st.write("hi")
        #st.write(response)
        return response
    except Exception as ex:
        print(ex)


def run_sql(query):
    with snowflake.connector.connect(
        account=secretstring['SNOWFLAKE_ACCOUNT'],
        user=secretstring['SNOWFLAKE_USER'],
        password=secretstring['SNOWFLAKE_PASSWORD'],
        warehouse=secretstring['SNOWFLAKE_WAREHOUSE'],
        database=secretstring['SNOWFLAKE_DATABASE'],
        schema=secretstring['SNOWFLAKE_SCHEMA']

    ) as conn:
        df = pd.read_sql(query, conn)
    return df




# --- Node 2: Execute SQL ---
def execute_sql(state: GraphState) -> GraphState:
    try:
        if state.get("error"):
            return state
        #df = run_sql(state["sql"]).head(10)
        #st.write(state["sql"])
        df=run_sql(state["sql"].replace("\n"," "))
        if len(df)>5000:
            state["error"] = "Please refine your prompt as the result returned is above the threshold (5000 records)"
            return state

        #st.write(df)
        #execute_sql='EXECUTE '+state["sql"]
        #print(execute_sql)
        #cur.execute(execute_sql)
        #state["sql"]=clean_sql(state["sql"])    
        state["df"] = df.to_dict(orient='records')
        #st.write(state)
    except Exception as e:
        state["error"] = f"SQL execution failed: {e}"
    return state

def generate_sql(state: GraphState) -> GraphState:
    try:
        payload = {"callwhichfunction": "generate_sql","inputs": state , "Content-Type":"application/json"}
        response=getQuery(payload)
        # Process the respnse if InvocationType is 'RequestResponse'
        #if 'Payload' in response:

        response_payload=response.json()
        #sql_query=response['sql']
        #st.write(response_payload)


        state["sql"] = response_payload["sql"]
    except Exception as e:
        state["error"] = f"SQL generation failed: {e}"
    return state
    
def summarize(state: GraphState) -> GraphState:
    try:
        #st.write(state)
        if state.get("error"):
            #st.write("return summarize")
            return state
        #st.write("hakshkjahs")
        payload = {"callwhichfunction": "summarize","inputs": state, "Content-Type":"application/json"}
        #st.write(json.dumps(payload))
        response=getQuery(payload)
        #st.write("hakshkjahs")
        #st.write(response)
        # Process the response if InvocationType is 'RequestResponse'
        #if 'Payload' in response:
        response_payload=response.json()
        state["summary"] = response_payload["summary"]
        #st.write(state)
    except Exception as e:
        state["error"] = f"SQL generation failed: {e}"
    return state



def route_after_converse(state: GraphState) -> str:
    """Decide whether to rerun SQL or just resummarize existing data."""
    q = (state.get("question") or "").lower()

    # phrases that imply a new slice/filter -> new SQL
    sql_triggers = [
        "show", "filter", "where", "by", "only", "for", "break down", 
        "group", "limit", "include", "exclude", "compare"
    ]

    # analytical language -> summarize existing df
    insight_triggers = [
        "trend", "increase", "decrease", "growth", "insight", "average",
        "highest", "lowest", "explain", "describe", "summary", "trendline",
        "pattern"
    ]

    if any(p in q for p in insight_triggers):
        return "summarize"     # reuse existing df
    if any(p in q for p in sql_triggers):
        return "generate_sql"  # need new data
    return "summarize"



def route_after_summarize(state: GraphState) -> str:
    """Decide where to go after summarization."""
    q = (state.get("question") or "").lower()

    followup_triggers = [
        "what about",
        "instead",
        "change",
        "filter",
        "by program area",
        "can you",
        "show only",
        "break down",
        "break it down",
    ]

    if any(phrase in q for phrase in followup_triggers):
        return "converse"
    return "END"


def converse(state: GraphState) -> GraphState:
    """Refine follow-up questions using conversation + prior result context."""
    try:
        #st.write(state)
        if state.get("error"):
            #st.write("return summarize")
            return state
        #st.write("hakshkjahs")
        payload = {"callwhichfunction": "converse","inputs": state, "Content-Type":"application/json"}
        #st.write(json.dumps(payload))
        response=getQuery(payload)
        #st.write("hakshkjahs")
        #st.write(response)
        # Process the response if InvocationType is 'RequestResponse'
        #if 'Payload' in response:
        response_payload=response.json()
        state["summary"] = response_payload["summary"]
        #st.write(state)
    except Exception as e:
        state["error"] = f"SQL generation failed: {e}"
    return state




# Build the workflow
graph = StateGraph(GraphState)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_node("summarize", summarize)
graph.add_node("converse", converse)

# Flow
graph.set_entry_point("generate_sql")
graph.add_edge("generate_sql", "execute_sql")
#graph.add_edge("execute_sql", END)
graph.add_edge("execute_sql", "summarize")
graph.add_edge("summarize", END)

# 👇 New conditional routing here
graph.add_conditional_edges(
    "summarize", 
    route_after_summarize, 
    {"converse": "converse", "END": END}
)

app = graph.compile()


    
# --- STREAMLIT UI ---

#st.set_page_config(layout="wide")

#st.markdown(
#    """
#    <style>
#    @font-face {
#        font-family: 'Everyday Sans';
#        src: url('path/to/everyday-sans.woff2') format('woff2');
#    }
#    body, .stApp, .sidebar .sidebar-content {
#        font-family: 'Everyday Sans', sans-serif;
#    }
#    </style>
#    """,
#    unsafe_allow_html=True
#
#)

st.markdown("""
    <style>
    button[data-baseweb="tab"] > div {
        font-size: 25px !important;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

#st.title("HRSA Conversational Agent Domain: Grants")
st.set_page_config(layout="wide")
st.title("💡 HRSA Conversational Agent (Bedrock Claude + Snowflake)")

# âœ… ensure these exist before you use them
if "history" not in st.session_state:
    st.session_state["history"] = []

if "context" not in st.session_state:
    st.session_state["context"] = ""


tab1, tab2, tab3 = st.tabs(["Home", "Solution Architecture", "Enhance & Scale"])




with tab3:
    st.markdown("### Functional Enhancements")
    st.markdown(
        """
        - **Role-based access controls**, Authentication
        - **Limit rows returned** with user-friendly message
        - **Consistent UI/UX** → design wireframe for improved experience
        - **Cost estimate** preview before execution
        - **Onboard additional datasets** for extended coverage
        """
    )

    st.markdown("---")  # Divider line

    st.markdown("### Non-Functional Enhancements")
    st.markdown(
        """
        - **Vectorization of metadata** → improve accuracy
        - **Automate metadata sync** with data source
        - **Performance optimization** (query, cache, API tuning)
        - **Concurrency & scalability** improvements
        - **Data security** → encryption, masking, DDOS & penetration testing
        - **Logging & auditing** for governance
        """
    )


with tab2:
    st.header("Architecture Diagram")
    st.image("hrsa_arch.png", caption="High Level Architecture", use_container_width=True)

with tab1:
    st.sidebar.image("hrsalogo.png", use_container_width=True)
    st.sidebar.title("Output Settings")
    show_sql = st.sidebar.checkbox("Show SQL", value=True, key="show_sql")
    show_table = st.sidebar.checkbox("Show Table", value=False, key="show_table")
    show_chart = st.sidebar.checkbox("Show Chart", value=True, key="show_chart")
    show_summary = st.sidebar.checkbox("Show Summary", value=True, key="show_summary")
    #st.sidebar.checkbox("Show Follow-up Questions", value=True, key="show_followup")

    user_q = st.text_area("Ask your question:")
    
    #mode = st.radio("Choose Agent Mode:", ["LangChain"])

    if st.button("Run Query"):
        st.session_state["history"].append({"role": "user", "content": user_q})
        inputs = {"question": user_q, "sql": None, "df": None, "summary": None, "error": None, "history": st.session_state["history"],"context": st.session_state["context"]}
        result = app.invoke(inputs)
        st.session_state["history"] = result["history"]
        st.session_state["context"] = result.get("context", st.session_state.get("context", ""))
        print(st.session_state["history"])
        print("Context info below")
        print(st.session_state["context"])
        if result.get("error"):
            st.error(result["error"])
        else:
            #df = run_sql(sql_query)
            if show_sql:
                st.subheader("Generated SQL")
                st.code(result["sql"], language="sql")
            if show_table:
                st.subheader("Results")
                st.dataframe(pd.DataFrame(result["df"]))
            if show_chart and result["df"] is not None and pd.DataFrame(result["df"]).shape[1] >= 2:
                st.subheader("Visualization")

                x_axis = st.selectbox("Select X-axis:", pd.DataFrame(result["df"]).columns, index=0)
                #y_axis = st.selectbox("Select Y-axis:", pd.DataFrame(result["df"]).columns, index=2)
                y_axis = st.selectbox("Select Y-axis:", pd.DataFrame(result["df"]).columns, index=len(pd.DataFrame(result["df"]).columns)-1)
                #color_axis = st.selectbox("Select Color (optional):", [None] + list(pd.DataFrame(result["df"]).columns), index=1)
                if x_axis and y_axis:
                    fig = px.bar(pd.DataFrame(result["df"]), x=x_axis, y=y_axis, title=f"{y_axis} vs {x_axis}")
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Please select at least an X and Y axis to plot.") 
            # Show Summary
            if show_summary:
                # Convert small sample of df to text for summary context
                #response = llm.invoke(summary_prompt)
                st.subheader("📊 Summary")
                st.write(result["summary"].replace('\n','\n'))
            
            st.success("✅ Query succeeded using AWS Bedrock")
            st.stop()
            
    # ✅ Add Examples section at the bottom 
    st.markdown("---")
    st.header("Examples")
    st.markdown("""
    - **Top 10 (based on $$ received)** Grantees received funds via multiple programs for FY2023.
    - **What activity codes** gave out the most awards (count and financial amount) in each past fiscal year?
    - **Total funding amount** given to organizations who received their first HRSA grant in FY2023.
    - **Percentage of funds** provided to "US Mexico Border Counties" compared to other counties for Arizona, California, New Mexico & Texas states across years.  
    - **Health Workforce** funding broken up by State over the past 3 fiscal years.
    - **Total funding amount** given to grant recipients who had no prior grants before October 1, 2022
    - **What was the distribution** of funding to states for H80 grant code?
    - **Show me the historical** grant funding in Virginia 5th Congressional District over the past 7 years, broken up by Program Area
    """)

