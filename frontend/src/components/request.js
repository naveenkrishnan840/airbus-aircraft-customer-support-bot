
export const RequestService = async (path, data) => {
    const header_data = {
        'Content-Type': 'application/json'
    }
    if (localStorage.getItem("token")){
        header_data["Authorization"] = `Bearer ${localStorage.getItem("token")}`
    }
    var body = JSON.stringify(data) 
    var path = `http://127.0.0.1:8005${path}`
    return await fetch(path, {
        method: "POST",
        headers: header_data,
        body: body
    })
}

