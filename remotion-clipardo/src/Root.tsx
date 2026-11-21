import { MyComposition } from "./Composition";
import { Bocetos } from "./Logos";
import { Bocetos2 } from "./Logos2";
import { LogosCuentas } from "./LogosCuentas";
import { LogosV2 } from "./LogosV2";
import { LogosV3 } from "./LogosV3";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Bocetos />
      <Bocetos2 />
      <LogosCuentas />
      <LogosV2 />
      <LogosV3 />
    </>
  );
};
