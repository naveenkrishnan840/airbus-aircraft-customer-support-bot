import {React, useState, useEffect} from "react";
import {TextareaAutosize} from "@mui/base";
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select from '@mui/material/Select';
import "react-chat-elements/dist/main.css"
import {MessageBox, MessageList } from "react-chat-elements";
import {Formik, Form, Field} from "formik";
import {RequestService} from "./request"
import parse from 'html-react-parser';
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Button from '@mui/material/Button';

const ChatBotBody = () => {
    const [passengerId, setPassengerId] = useState("");
    const [open, setOpen] = useState(false);
    // const handleOpen = () => {
    //     setOpen(true);
    // };
    const handleClose = () => {
        setOpen(false);
        const data = {"input_msg": "", "passengerId": passengerId}
        const response = RequestService("/bot-message-request", data);
        response.then((res)=>{
            if (res.detail){
                if (res.detail.bot_response){
                    setMessages((prevMsg)=>
                        [...prevMsg, {
                            position: "left",
                            type: "text",
                            title: "Bot",
                            text: parse(res.detail),
                            // styles: {backgroundColor:"gray"},
                            className: "text-black",
                            date: new Date()
                        }]
                    )
                } else {
                    <>
                        <Modal
                            open={open}
                            aria-labelledby="parent-modal-title"
                            aria-describedby="parent-modal-description"
                        >
                            <Box sx={{ ...style, width: 400 }}>
                            <h2 id="parent-modal-title">Text in a modal</h2>
                            <p id="parent-modal-description">
                            Do you approve of the above actions? Type 'yes' to continue;
                            otherwise, explain your requested changed."
                            </p>
                            <Button onClick={handleClose}>Yes</Button>
                            <Button onClick={handleClose}>No</Button>
                            </Box>
                        </Modal>
                    </>
                }
            }
        })
        
    };
    const style = {
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 400,
        bgcolor: 'background.paper',
        border: '2px solid #000',
        boxShadow: 24,
        pt: 2,
        px: 4,
        pb: 3,
      };
    const [messages, setMessages] = useState([{
            position: "left",
            type: "text",
            title: "Bot",
            text: "Hi, How can i help you!",
            focus: true,
            className: "text-black max-h-screen",
            date: new Date()
            }]);
    const onSubmitForm = (inputMessage) => {
        const data = {"input_msg": inputMessage["inputmessage"], "passengerId": passengerId}
        const response = RequestService("/bot-message-request", data);
        response.then((res)=>{
            if (res.detail){
                if (res.detail.bot_response){
                    setMessages((prevMsg)=>
                        [...prevMsg, {
                            position: "left",
                            type: "text",
                            title: "Bot",
                            text: parse(res.detail),
                            // styles: {backgroundColor:"gray"},
                            className: "text-black",
                            date: new Date()
                        }]
                    )
                } else {
                    <>
                        <Modal
                            open={open}
                            aria-labelledby="parent-modal-title"
                            aria-describedby="parent-modal-description"
                        >
                            <Box sx={{ ...style, width: 400 }}>
                            <h2 id="parent-modal-title">Text in a modal</h2>
                            <p id="parent-modal-description">
                            Do you approve of the above actions? Type 'yes' to continue;
                            otherwise, explain your requested changed."
                            </p>
                            <Button onClick={handleClose}>Yes</Button>
                            <Button onClick={handleClose}>No</Button>
                            </Box>
                        </Modal>
                    </>
                }
            }
        })
    }
    const handlePassengerId = (evt) => {
        setPassengerId(evt.target.value)
    }
    useEffect(() => {
        RequestService("/compile-langgraph", [])
      }, []);
    return (
        <>
    <div className="flex flex-col mx-40 border-green-700 overflow-y-auto max-h-80 text-white">
        <MessageList lockable={true} className="h-80 overflow-y-auto overflow-hidden " dataSource={messages} />
    </div>
    <Formik
        validateOnBlur={false}
        validateOnChange={false}
            initialValues={{ inputmessage: ""}}
            onSubmit={async (values, { resetForm }) => {
                setMessages((prevMsg)=>
                    [...prevMsg, {
                        position: "right",
                        type: "text",
                        title: "User",
                        text: values.inputmessage,
                        className: "text-black",
                        // styles: {"color":"#2f2f2f"},
                        date: new Date()
                    }]
                )
                onSubmitForm(values)
                resetForm({
                    values: { inputmessage: "",  passengerId: null}
                })
            }}
            // validationSchema={}
        >
            {({ values, submitForm, errors }) => (
                <Form>
                    <Field name="inputmessage" >
                        {({ field }) => (
                            <>
                                <FormControl sx={{ m: 1, width: 500, marginLeft: 40 }}>
                                    <InputLabel id="demo-simple-select-standard-label">Passenger Id</InputLabel>
                                    <Select
                                    labelId="demo-simple-select-standard-label"
                                    id="demo-simple-select-standard"
                                    value={passengerId}
                                    onChange={handlePassengerId}
                                    label="Passenger ID"
                                    defaultValue={"None"}
                                    >
                                    <MenuItem value="">
                                        <em>None</em>
                                    </MenuItem>
                                    <MenuItem value={"5763 808478"}>{"5763 808478"}</MenuItem>
                                    <MenuItem value={"0990 692076"}>{"0990 692076"}</MenuItem>
                                    <MenuItem value={"0990 692076"}>{"7352 229580"}</MenuItem>
                                    <MenuItem value={"9420 542320"}>{"9420 542320"}</MenuItem>
                                    <MenuItem value={"5356 110572"}>{"5356 110572"}</MenuItem>
                                    {/* {[,,"0990 692076","9420 542320","5356 110572"].map((val) =>
                                        <>
                                            <MenuItem value={val}>{val}</MenuItem>
                                        </>
                                    )} */}
                                    </Select>
                                </FormControl>
                                <div className="group flex my-18 mx-40">
                                    <div style={{background: "#2f2f2f"}} id="composer-background" className="flex w-full cursor-text flex-col rounded-3xl px-2.5 py-1 transition-colors contain-inline-size bg-[#f4f4f4] dark:bg-token-main-surface-secondary">
                                        <div className="flex min-h-[44px] items-center px-2" style={{color: "white"}}>
                                            <div className="max-w-full flex-1">
                                                <div className="text-token-text-primary  overflow-auto default-browser">
                                                    <TextareaAutosize onChange={submitForm} {...field} style={{color: "white", maxHeight: "70px"}} className="chat-bot focus:outline-none block h-10 w-full resize-none border-0 bg-transparent px-0 py-2 text-token-text-primary placeholder:text-token-text-secondary" autoFocus="" placeholder="Message ChatGPT">
                                                    </TextareaAutosize>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex h-[44px] items-center justify-between">
                                        <div className="flex gap-x-1">
                                            <div className="relative">
                                                <div className="relative">
                                                    <div className="flex flex-col">
                                                        {/* <input multiple="" tabindex="-1" class="hidden" type="file" style={{display: "none"}}/> */}
                                                        {/* <span class="hidden"></span> */}
                                                        {/* <button type="button" id="radix-:rb:" aria-haspopup="menu" aria-expanded="false" data-state="closed" class="text-token-text-primary border border-transparent inline-flex items-center justify-center gap-1 rounded-lg text-sm dark:transparent dark:bg-transparent leading-none outline-none cursor-pointer hover:bg-token-main-surface-secondary dark:hover:bg-token-main-surface-secondary focus-visible:bg-token-main-surface-secondary radix-state-active:text-token-text-secondary radix-disabled:cursor-auto radix-disabled:bg-transparent radix-disabled:text-token-text-tertiary dark:radix-disabled:bg-transparent m-0 h-0 w-0 border-none bg-transparent p-0"></button> */}
                                                        {/* <span class="flex" data-state="closed">
                                                            <button disabled="" aria-disabled="true" aria-label="Attach files is unavailable" class="flex items-center justify-center h-8 w-8 rounded-lg rounded-bl-xl text-token-text-primary dark:text-white focus-visible:outline-black dark:focus-visible:outline-white opacity-30"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                <path fill-rule="evenodd" clip-rule="evenodd" d="M9 7C9 4.23858 11.2386 2 14 2C16.7614 2 19 4.23858 19 7V15C19 18.866 15.866 22 12 22C8.13401 22 5 18.866 5 15V9C5 8.44772 5.44772 8 6 8C6.55228 8 7 8.44772 7 9V15C7 17.7614 9.23858 20 12 20C14.7614 20 17 17.7614 17 15V7C17 5.34315 15.6569 4 14 4C12.3431 4 11 5.34315 11 7V15C11 15.5523 11.4477 16 12 16C12.5523 16 13 15.5523 13 15V9C13 8.44772 13.4477 8 14 8C14.5523 8 15 8.44772 15 9V15C15 16.6569 13.6569 18 12 18C10.3431 18 9 16.6569 9 15V7Z" fill="currentColor"></path></svg>
                                                            </button>
                                                        </span> */}
                                                        <div type="button" aria-haspopup="dialog" aria-expanded="false" aria-controls="radix-:re:" data-state="closed"></div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <span data-state="closed">
                                            <button onSubmit={submitForm} disabled="" aria-label="Send prompt" data-testid="send-button" className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:opacity-70 focus-visible:outline-none focus-visible:outline-black disabled:text-[#f4f4f4] disabled:hover:opacity-100 dark:focus-visible:outline-white disabled:dark:bg-token-text-quaternary dark:disabled:text-token-main-surface-secondary bg-black text-white dark:bg-white dark:text-black disabled:bg-[#D7D7D7]">
                                                <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="icon-2xl"><path fillRule="evenodd" clipRule="evenodd" d="M15.1918 8.90615C15.6381 8.45983 16.3618 8.45983 16.8081 8.90615L21.9509 14.049C22.3972 14.4953 22.3972 15.2189 21.9509 15.6652C21.5046 16.1116 20.781 16.1116 20.3347 15.6652L17.1428 12.4734V22.2857C17.1428 22.9169 16.6311 23.4286 15.9999 23.4286C15.3688 23.4286 14.8571 22.9169 14.8571 22.2857V12.4734L11.6652 15.6652C11.2189 16.1116 10.4953 16.1116 10.049 15.6652C9.60265 15.2189 9.60265 14.4953 10.049 14.049L15.1918 8.90615Z" fill="currentColor"></path></svg>
                                            </button>
                                        </span>
                                    </div>
                                    </div>
                                </div>
                            </>
                        )}
                    </Field>
                </Form>)}
        </Formik>
        </>
    )
}

export default ChatBotBody;