import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the application title and the synthetic data notice", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Immunization Decision Support System" })).toBeInTheDocument();
  expect(screen.getByText("All data shown is synthetic.")).toBeInTheDocument();
});
