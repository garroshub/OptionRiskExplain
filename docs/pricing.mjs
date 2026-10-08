// Browser-native Black-Scholes-Merton European pricing.
export const cdf=x=>{
  const z=Math.abs(x)/Math.SQRT2,t=1/(1+0.3275911*z);
  const erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-z*z);
  return 0.5*(1+(x<0?-erf:erf));
};
const pdf=x=>Math.exp(-x*x/2)/Math.sqrt(2*Math.PI);
export function priceOption({S,K,T,r,q,v}){
  if(![S,K,T,r,q,v].every(Number.isFinite)||S<0||K<=0||T<0||v<0)throw Error('Finite inputs required. Strike must be positive; spot, maturity and volatility must be nonnegative.');
  const empty={deltaCall:null,deltaPut:null,gamma:null,vega:null,thetaCall:null,thetaPut:null,rhoCall:null,rhoPut:null};
  if(T===0)return{call:Math.max(0,S-K),put:Math.max(0,K-S),...empty};
  const a=S*Math.exp(-q*T),b=K*Math.exp(-r*T);
  if(S===0||v===0)return{call:Math.max(0,a-b),put:Math.max(0,b-a),...empty};
  const d1=(Math.log(S/K)+(r-q+v*v/2)*T)/(v*Math.sqrt(T)),d2=d1-v*Math.sqrt(T);
  const theta=-a*pdf(d1)*v/(2*Math.sqrt(T));
  return{
    call:Math.max(0,a*cdf(d1)-b*cdf(d2)),put:Math.max(0,b*cdf(-d2)-a*cdf(-d1)),
    deltaCall:Math.exp(-q*T)*cdf(d1),deltaPut:Math.exp(-q*T)*(cdf(d1)-1),
    gamma:Math.exp(-q*T)*pdf(d1)/(S*v*Math.sqrt(T)),
    vega:a*pdf(d1)*Math.sqrt(T)/100,
    thetaCall:(theta-r*b*cdf(d2)+q*a*cdf(d1))/365,
    thetaPut:(theta+r*b*cdf(-d2)-q*a*cdf(-d1))/365,
    rhoCall:K*T*Math.exp(-r*T)*cdf(d2)/100,
    rhoPut:-K*T*Math.exp(-r*T)*cdf(-d2)/100
  };
}
