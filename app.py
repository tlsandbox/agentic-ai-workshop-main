import requests
import streamlit as st
import os
import uuid
from datetime import datetime

# Read configuration from secrets.toml or environment variables
BASE_API_URL = st.secrets.get("BASE_API_URL", os.getenv("BASE_API_URL", "http://localhost:7860"))
FLOW_ID = st.secrets.get("FLOW_ID", os.getenv("FLOW_ID", ""))
LANGFLOW_API_KEY = st.secrets.get("LANGFLOW_API_KEY", os.getenv("LANGFLOW_API_KEY", ""))

# Initialize session ID in session state
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())


def run_flow(message: str) -> dict:
    api_url = f"{BASE_API_URL}/api/v1/run/{FLOW_ID}?stream=false"

    payload = {
        "input_value": message,
        "output_type": "chat",
        "input_type": "chat",
        "session_id": st.session_state["session_id"]
    }

    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(
            f"Cannot connect to Langflow at {BASE_API_URL}. "
            f"Please ensure Langflow is running and accessible. "
            f"Error details: {str(e)}"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request to Langflow timed out. The server at {BASE_API_URL} may be slow or unresponsive.")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error from Langflow: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")


def main():
    # Apply custom styles
    st.markdown(
        """
        <style>
            .chat-bubble {
                background-color: #007bff;
                color: white;
                padding: 10px;
                border-radius: 15px;
                max-width: 80%;
                margin-bottom: 10px;
                font-size: 16px;
                line-height: 1.5;
            }
            .chat-bubble-user {
                background-color: #f1f1f1;
                color: black;
                padding: 10px;
                border-radius: 15px;
                max-width: 80%;
                margin-bottom: 10px;
                align-self: flex-end;
                font-size: 16px;
                line-height: 1.5;
            }
            .timestamp {
                font-size: 12px;
                color: gray;
                margin-bottom: 5px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📞 Customer Support Assistant")
    st.subheader("Get instant answers to your questions!")
    
    # Validate configuration
    if not FLOW_ID:
        st.error("⚠️ **Configuration Error**\n\n`FLOW_ID` is not configured. Please add it to `.streamlit/secrets.toml`:\n```toml\nFLOW_ID = \"your-flow-id-here\"\n```")
        st.stop()
    
    # Check Langflow connection status
    try:
        # Try to connect to the base URL or API endpoint
        test_headers = {}
        if LANGFLOW_API_KEY:
            test_headers["Authorization"] = f"Bearer {LANGFLOW_API_KEY}"
            test_headers["x-api-key"] = LANGFLOW_API_KEY
        
        test_response = requests.get(f"{BASE_API_URL}", timeout=2, headers=test_headers)
        auth_status = " (with API key)" if LANGFLOW_API_KEY else " (no API key configured)"
        st.success(f"✅ Langflow is reachable at `{BASE_API_URL}`{auth_status}")
    except requests.exceptions.ConnectionError:
        st.error(f"❌ **Cannot connect to Langflow** at `{BASE_API_URL}`\n\n**Please ensure:**\n- Langflow is running (try `langflow run` in terminal)\n- The URL and port are correct\n- No firewall is blocking the connection")
    except requests.exceptions.RequestException:
        # If we can't connect but it's not a connection error, still show a warning
        st.warning(f"⚠️ Unable to verify connection to Langflow at `{BASE_API_URL}`")

    # Initialize session state for messages
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "current_input" not in st.session_state:
        st.session_state["current_input"] = ""

    # Clear chat button
    if st.button("Clear Chat"):
        st.session_state["messages"] = []
        st.session_state["current_input"] = ""

    # Sample questions
    st.markdown("### Try asking:")
    col1, col2, col3 = st.columns(3)

    if col1.button("How can I track my order?"):
        st.session_state["current_input"] = "How can I track my order?"
    if col2.button("What is your return policy?"):
        st.session_state["current_input"] = "What is your return policy?"
    if col3.button("Can I cancel order #1004?"):
        st.session_state["current_input"] = "Can I cancel order #1004?"

    # Input form for question submission
    with st.form(key="chat_form", clear_on_submit=False):
        user_input = st.text_input(
            "Type your question here",
            placeholder="How can we help you today?",
            value=st.session_state["current_input"],
        )
        submit_button = st.form_submit_button("Submit")

    if submit_button:
        if not user_input.strip():
            st.error("Please enter a question.")
        else:
            try:
                response = run_flow(user_input)

                # Extract and store bot response - handle different response structures
                bot_response = ""
                if "outputs" in response and len(response["outputs"]) > 0:
                    # Try the cloud format first
                    try:
                        bot_response = response["outputs"][0]["outputs"][0]["results"]["message"]["text"]
                    except (KeyError, IndexError):
                        # Try alternative local OSS format
                        try:
                            bot_response = response["outputs"][0]["results"]["message"]["text"]
                        except (KeyError, IndexError):
                            # Try direct message format
                            try:
                                bot_response = response["message"]["text"]
                            except (KeyError, IndexError):
                                # Fallback: try to get any text from results
                                if "results" in response:
                                    bot_response = str(response["results"])
                                else:
                                    bot_response = str(response)
                else:
                    # If no outputs, try direct response
                    bot_response = str(response.get("message", response.get("text", response)))
                
                if not bot_response:
                    bot_response = "No response received from the assistant."
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Add the latest interaction to the chat history
                st.session_state["messages"].insert(0, {"user": user_input, "bot": bot_response, "timestamp": timestamp})
                # Clear the current input
                st.session_state["current_input"] = ""

            except ConnectionError as e:
                st.error(f"🔌 **Connection Error**\n\n{str(e)}\n\n**Troubleshooting steps:**\n1. Make sure Langflow is running on `{BASE_API_URL}`\n2. Check if the port number is correct (default is 7860)\n3. Verify Langflow is accessible by visiting `{BASE_API_URL}` in your browser")
            except TimeoutError as e:
                st.error(f"⏱️ **Timeout Error**\n\n{str(e)}")
            except Exception as e:
                error_msg = str(e)
                if "Connection refused" in error_msg or "Failed to establish" in error_msg:
                    st.error(f"🔌 **Cannot connect to Langflow**\n\nPlease ensure Langflow is running at `{BASE_API_URL}`\n\n**To start Langflow:**\n- Run `langflow run` in your terminal\n- Or check if it's running on a different port")
                else:
                    st.error(f"❌ **Error**\n\n{error_msg}\n\nPlease check your Langflow configuration and try again.")

    # Display chat history (latest at the top)
    for message in st.session_state["messages"]:
        # Timestamp
        st.markdown(f'<div class="timestamp">{message["timestamp"]}</div>', unsafe_allow_html=True)
        # User's message
        st.markdown(
            f'<div class="chat-bubble-user">{message["user"]}</div>',
            unsafe_allow_html=True,
        )
        # Bot's response
        st.markdown(
            f'<div class="chat-bubble">{message["bot"]}</div>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
