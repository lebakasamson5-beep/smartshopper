let userLatitude = null;
let userLongitude = null;


function useMyLocation() {

    const status = document.getElementById("status");

    if (!navigator.geolocation) {

        status.innerText =
            "Your browser does not support location services.";

        return;
    }

    status.innerText =
        "Getting your location...";


    navigator.geolocation.getCurrentPosition(

        function(position) {

            userLatitude =
                position.coords.latitude;

            userLongitude =
                position.coords.longitude;

            status.innerText =
                "Location found successfully.";

            document.getElementById("location").value =
                "Current location";

        },

        function(error) {

            status.innerText =
                "Unable to get your location. Please enter it manually.";

        }

    );

}


async function searchProducts() {

    const product =
        document.getElementById("product").value.trim();

    const status =
        document.getElementById("status");

    const results =
        document.getElementById("results");


    if (!product) {

        status.innerText =
            "Please enter a product.";

        return;
    }


    if (userLatitude === null ||
        userLongitude === null) {

        status.innerText =
            "Please select your location first.";

        return;
    }


    status.innerText =
        "Searching nearby stores...";

    results.innerHTML = "";


    try {

        const response = await fetch(
            "/locations/search",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    latitude: userLatitude,

                    longitude: userLongitude,

                    product: product

                })

            }
        );


        const data =
            await response.json();


        if (!data.success) {

            status.innerText =
                data.message;

            return;
        }


        status.innerText =
            `Found ${data.stores.length} nearby stores.`;


        if (data.stores.length === 0) {

            results.innerHTML =
                "<p>No nearby stores found.</p>";

            return;
        }


        data.stores.forEach(store => {

            const card =
                document.createElement("div");

            card.className =
                "store-card";


            card.innerHTML = `

                <h2>${store.name}</h2>

                <p>
                    ${store.address || ""}
                </p>

                <p>
                    <strong>
                        ${store.distance_km} km away
                    </strong>
                </p>

                ${
                    store.price
                    ? `<p>Price: R${store.price}</p>`
                    : ""
                }

            `;


            results.appendChild(card);

        });


    } catch (error) {

        console.error(error);

        status.innerText =
            "Something went wrong while searching.";

    }

}
