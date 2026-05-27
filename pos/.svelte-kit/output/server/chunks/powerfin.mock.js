const MOCK_USER = {
  user_id: 3,
  name: "Carlos Sarmiento",
  role: "DISPATCHER",
  location_id: 1,
  location_name: "NEOPAUTE"
};
const MOCK_CUSTOMERS = [
  {
    customer_id: "0912345678",
    id_type: "CED",
    id_number: "0912345678",
    name: "Juan Carlos Pérez",
    email: "jperez@email.com",
    phone: "0991234567",
    price_list: "VIP",
    price_list_name: "Cliente VIP",
    credit_active: false,
    credit_balance: 0,
    plates: ["ABC-1234"]
  },
  {
    customer_id: "1790012345001",
    id_type: "RUC",
    id_number: "1790012345001",
    name: "Transportes Andinos S.A.",
    email: "trans@andinos.com",
    phone: "022345678",
    price_list: "STANDARD",
    price_list_name: "Precio Normal",
    credit_active: true,
    credit_balance: 500,
    plates: ["XYZ-5678", "XYZ-5679"]
  }
];
function delay(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
let mockToken = "";
async function login(data) {
  await delay(500);
  if (data.pin === "1234") {
    mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock_token";
    return {
      access_token: mockToken,
      expires_in: 28800,
      user: { ...MOCK_USER, name: data.username }
    };
  }
  throw new Error("Credenciales inválidas");
}
async function getCustomerPrice(_token, customerId, _gradeId) {
  await delay(200);
  const customer = MOCK_CUSTOMERS.find((c) => c.customer_id === customerId);
  const unitPrice = customer?.price_list === "VIP" ? 1.1 : 1.5;
  return {
    grade_id: "SUPER",
    grade_name: "Gasolina Super",
    unit_price: unitPrice,
    price_list: customer?.price_list ?? "STANDARD",
    currency: "USD"
  };
}
export {
  getCustomerPrice as g,
  login as l
};
