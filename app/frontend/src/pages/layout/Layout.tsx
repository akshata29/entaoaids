import { useState } from "react";
import { Outlet, NavLink, Link } from "react-router-dom";
import { Checkbox, Panel, DefaultButton} from "@fluentui/react";

import github from "../../assets/github.svg"

import styles from "./Layout.module.css";


const Layout = () => {
    const [isConfigPanelOpen, setIsConfigPanelOpen] = useState(false);

    return (
        <div className={styles.layout}>
            <header className={styles.header} role={"banner"}>
                <div className={styles.headerContainer}>
                    <Link to="https://dataaipdfchat.azurewebsites.net/" target={"_blank"} className={styles.headerTitleContainer}>
                        <h3 className={styles.headerTitle}>Document Summarization</h3>
                    </Link>
                    <nav>
                        <ul className={styles.headerNavList}>
                            <li className={styles.headerNavLeftMargin}>
                                <NavLink to="/" className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}>
                                Upload &nbsp;&nbsp;&nbsp;
                                </NavLink>
                            </li>
                            <li className={styles.headerNavLeftMargin}>
                                <NavLink to="/summary" className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}>
                                    Summarization
                                </NavLink>
                            </li>
                            <li className={styles.headerNavLeftMargin}>
                                <a href="https://github.com/akshata29/entaoaids" target={"_blank"} title="Github repository link">
                                    <img
                                        src={github}
                                        alt="Github logo"
                                        aria-label="Link to github repository"
                                        width="20px"
                                        height="20px"
                                        className={styles.githubLogo}
                                    />
                                </a>
                            </li>
                        </ul>
                    </nav>
                    <h4 className={styles.headerRightText}>Azure OpenAI</h4>
                </div>
            </header>
            <Outlet />
        </div>
    );
};

export default Layout;